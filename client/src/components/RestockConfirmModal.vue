<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">{{ t('restocking.confirmTitle') }}</h3>
            <button type="button" class="close-button" :aria-label="t('common.close')" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <p class="confirm-message">{{ t('restocking.confirmMessage') }}</p>

            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>{{ t('restocking.table.sku') }}</th>
                    <th>{{ t('restocking.table.item') }}</th>
                    <th>{{ t('restocking.table.quantity') }}</th>
                    <th>{{ t('restocking.table.lineTotal') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="line in lines" :key="line.item_sku">
                    <td><strong>{{ line.item_sku }}</strong></td>
                    <td>{{ translateProductName(line.item_name) }}</td>
                    <td>{{ line.quantity }}</td>
                    <td>{{ formatCurrency(line.line_total, currentCurrency) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="summary-grid">
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.total') }}</div>
                <div class="summary-value">{{ formatCurrency(total, currentCurrency) }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.leadTime') }}</div>
                <div class="summary-value">{{ t('restocking.days', { days: leadTimeDays }) }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.expectedDelivery') }}</div>
                <!-- Client-side preview only - the server response is authoritative -->
                <div class="summary-value">{{ formatDate(expectedDelivery) }}</div>
              </div>
            </div>

            <div v-if="error" class="error">{{ error }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" :disabled="submitting" @click="close">
              {{ t('restocking.cancel') }}
            </button>
            <button class="btn-primary" :disabled="submitting" @click="confirm">
              {{ submitting ? t('restocking.submitting') : t('restocking.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  lines: {
    type: Array,
    default: () => []
  },
  total: {
    type: Number,
    default: 0
  },
  leadTimeDays: {
    type: Number,
    default: 0
  },
  expectedDelivery: {
    type: [String, Date],
    default: null
  },
  submitting: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['close', 'confirm'])

const close = () => {
  if (props.submitting) return
  emit('close')
}

const confirm = () => {
  // Guard against double-submit from a fast double-click before the
  // `submitting` prop update from the parent re-renders this button.
  if (props.submitting) return
  emit('confirm')
}

const formatDate = (value) => {
  if (!value) return 'N/A'

  let date
  if (value instanceof Date) {
    date = value
  } else if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    // Date-only strings parse as UTC midnight, which can render as the
    // previous day locally - build the local calendar date instead.
    const [y, m, d] = value.split('-').map(Number)
    date = new Date(y, m - 1, d)
  } else {
    date = new Date(value)
  }

  if (isNaN(date.getTime())) return 'N/A'
  const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
  return date.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.confirm-message {
  color: #334155;
  font-size: 0.938rem;
  margin-bottom: 1.25rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-top: 1.25rem;
}

.summary-item {
  padding: 1rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.375rem;
}

.summary-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary {
  padding: 0.625rem 1.25rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary:disabled,
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
