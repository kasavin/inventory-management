<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>

        <div class="slider-row">
          <label for="budget-slider">{{ t('restocking.budget') }}</label>
          <input
            id="budget-slider"
            v-model.number="budget"
            type="range"
            min="0"
            step="100"
            :max="maxBudget"
            :aria-valuetext="formatCurrency(budget, currentCurrency)"
            class="budget-slider"
          />
          <span class="slider-value">{{ formatCurrency(budget, currentCurrency) }}</span>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">{{ t('restocking.budget') }}</div>
            <div class="stat-value">{{ formatCurrency(budget, currentCurrency) }}</div>
          </div>
          <div class="stat-card success">
            <div class="stat-label">{{ t('restocking.recommendedTotal') }}</div>
            <div class="stat-value">{{ formatCurrency(recommendation.total, currentCurrency) }}</div>
          </div>
          <div class="stat-card info">
            <div class="stat-label">{{ t('restocking.remaining') }}</div>
            <div class="stat-value">{{ formatCurrency(recommendation.remaining, currentCurrency) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">{{ t('restocking.lineCount') }}</div>
            <div class="stat-value">{{ recommendation.lines.length }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
        </div>

        <div v-if="recommendation.lines.length === 0" class="no-data">
          {{ t('restocking.noRecommendations') }}
        </div>
        <template v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.item') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th>{{ t('restocking.table.quantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineTotal') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in recommendation.lines" :key="line.item_sku">
                  <td><strong>{{ line.item_sku }}</strong></td>
                  <td>{{ translateProductName(line.item_name) }}</td>
                  <td>
                    <span :class="['badge', line.trend]">{{ t(`trends.${line.trend}`) }}</span>
                  </td>
                  <td>
                    {{ line.quantity }}
                    <span v-if="line.partial" class="partial-flag">({{ t('restocking.partial') }})</span>
                  </td>
                  <!-- Unit costs need cents (e.g. $9.25) - whole-dollar rounding hides real price differences -->
                  <td>{{ formatCurrencyWithDecimals(line.unit_cost, currentCurrency, 2) }}</td>
                  <td><strong>{{ formatCurrency(line.line_total, currentCurrency) }}</strong></td>
                  <td>{{ t('restocking.days', { days: line.lead_time_days }) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="recommendation.excluded.length > 0" class="excluded-note">
            {{ t('restocking.excludedItems', { count: recommendation.excluded.length }) }}
          </p>
        </template>
      </div>

      <div class="place-order-row">
        <button
          class="po-button create"
          :disabled="recommendation.lines.length === 0 || submitting"
          @click="showConfirm = true"
        >
          {{ t('restocking.placeOrder') }}
        </button>

        <div v-if="successOrder" class="success-message">
          {{ t('restocking.success', { orderNumber: successOrder.order_number }) }}
          <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
        </div>
      </div>
    </div>

    <RestockConfirmModal
      :is-open="showConfirm"
      :lines="recommendation.lines"
      :total="recommendation.total"
      :lead-time-days="previewLeadTimeDays"
      :expected-delivery="previewExpectedDelivery"
      :submitting="submitting"
      :error="submitError"
      @close="showConfirm = false"
      @confirm="placeOrder"
    />
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'
import { fullRestockCost, recommendRestock } from '../utils/restock'
import RestockConfirmModal from '../components/RestockConfirmModal.vue'

export default {
  name: 'Restocking',
  components: { RestockConfirmModal },
  setup() {
    // Restocking is intentionally NOT wired to the global FilterBar - the
    // budget/recommendation logic here is independent of warehouse/category/
    // month/status filters, so there are no filter watchers in this view.
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])

    // Budget is always tracked in USD internally (slider min/max/step are
    // USD amounts). formatCurrency() below converts to yen for display only
    // when the locale is Japanese - it never mutates the underlying number.
    const budget = ref(0)
    let budgetInitialized = false

    const showConfirm = ref(false)
    const submitting = ref(false)
    const submitError = ref(null)
    const successOrder = ref(null)

    // Rounded UP to the nearest $100 so the slider always covers the full
    // restock cost of every forecasted item.
    const maxBudget = computed(() => Math.ceil(fullRestockCost(forecasts.value) / 100) * 100)

    const recommendation = computed(() => recommendRestock(forecasts.value, budget.value))

    // Highest lead time among recommended lines - used as a client-side
    // preview only. The server response is authoritative once the order is
    // actually submitted.
    const previewLeadTimeDays = computed(() => {
      if (recommendation.value.lines.length === 0) return 0
      return Math.max(...recommendation.value.lines.map(l => l.lead_time_days))
    })

    const previewExpectedDelivery = computed(() => {
      if (recommendation.value.lines.length === 0) return null
      const date = new Date()
      date.setDate(date.getDate() + previewLeadTimeDays.value)
      return date
    })

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()

        // Default the budget to half the full restock cost (rounded to the
        // nearest $100), but only the first time data loads so we don't
        // clobber a budget the user already adjusted.
        if (!budgetInitialized) {
          budget.value = Math.round((maxBudget.value / 2) / 100) * 100
          budgetInitialized = true
        }
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      // Guard against double-submit (e.g. a fast double-click on Confirm).
      if (submitting.value) return

      submitting.value = true
      submitError.value = null
      try {
        const lines = recommendation.value.lines.map(l => ({
          item_sku: l.item_sku,
          quantity: l.quantity
        }))
        const order = await api.createRestockOrder(lines)
        successOrder.value = order
        showConfirm.value = false
      } catch (err) {
        // Keep the modal open and surface the server's detail message.
        // FastAPI validation (422) errors send `detail` as an array of
        // {msg, ...} objects rather than a string - normalize both shapes.
        const detail = err.response?.data?.detail
        if (typeof detail === 'string') {
          submitError.value = detail
        } else if (Array.isArray(detail)) {
          submitError.value = detail.map(d => d.msg).join('; ')
        } else {
          submitError.value = t('restocking.submitError') + ': ' + err.message
        }
      } finally {
        submitting.value = false
      }
    }

    // If the budget slider is dragged back down below what's already been
    // recommended, clear any stale success message from a previous order.
    watch(budget, () => {
      successOrder.value = null
    })

    onMounted(loadForecasts)

    return {
      t,
      currentCurrency,
      translateProductName,
      formatCurrency,
      formatCurrencyWithDecimals,
      loading,
      error,
      budget,
      maxBudget,
      recommendation,
      showConfirm,
      submitting,
      submitError,
      successOrder,
      previewLeadTimeDays,
      previewExpectedDelivery,
      placeOrder
    }
  }
}
</script>

<style scoped>
.slider-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.slider-row label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  flex-shrink: 0;
}

.budget-slider {
  flex: 1;
  accent-color: #3b82f6;
}

.slider-value {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
  flex-shrink: 0;
  min-width: 90px;
  text-align: right;
}

.no-data {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.875rem;
}

.partial-flag {
  color: #ea580c;
  font-size: 0.75rem;
  font-weight: 600;
}

.excluded-note {
  margin-top: 0.875rem;
  color: #64748b;
  font-size: 0.813rem;
  font-style: italic;
}

.place-order-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  margin-top: 1.25rem;
}

.po-button {
  padding: 0.625rem 1.25rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.po-button.create {
  background: #3b82f6;
  color: white;
}

.po-button.create:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.po-button.create:disabled {
  background: #cbd5e1;
  color: #64748b;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.success-message {
  background: #d1fae5;
  color: #065f46;
  padding: 0.625rem 1rem;
  border-radius: 8px;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.success-message a {
  color: #065f46;
  font-weight: 700;
  text-decoration: underline;
}
</style>
