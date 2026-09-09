// Pure helpers for the Restocking tab. No Vue imports here so this stays
// easy to reason about (and test) in isolation from component state.

// Trend priority for the "priority fill" rule below: items with increasing
// demand are restocked first, then stable, then decreasing - restocking a
// decreasing-demand item is the lowest-value use of a limited budget.
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

// Round to the nearest cent so repeated multiplication/subtraction on money
// values doesn't accumulate floating point drift (e.g. 0.1 + 0.2 !== 0.3).
function roundCents(amount) {
  return Math.round(amount * 100) / 100
}

// Until the backend ships unit_cost, or if a forecast is otherwise missing
// pricing or has zero demand, treat it as not restockable rather than
// computing with NaN/0 - a zero-demand forecast would produce a 0-quantity
// line, which the server rejects with a 422.
function isRestockable(forecast) {
  return typeof forecast.unit_cost === 'number' &&
    forecast.unit_cost > 0 &&
    forecast.forecasted_demand > 0
}

// Total cost (USD) of restocking every restockable forecast up to its
// forecasted_demand.
export function fullRestockCost(forecasts) {
  return roundCents(
    forecasts
      .filter(isRestockable)
      .reduce((sum, f) => sum + f.forecasted_demand * f.unit_cost, 0)
  )
}

// Recommend which forecasts to restock, and how much of each, given a
// budget (USD).
//
// Rule ("priority fill"):
//   1. Sort candidates by trend rank (increasing < stable < decreasing),
//      then by larger growth (forecasted_demand - current_demand) first,
//      then by SKU as a stable tie-break.
//   2. Walk the sorted list, taking the FULL forecasted quantity for each
//      line while it still fits in the remaining budget.
//   3. The first line that doesn't fully fit gets a partial quantity
//      (floor(remaining / unit_cost)) if that's at least 1 unit, and is
//      flagged partial.
//   4. Then STOP - every later candidate is excluded even if it would have
//      been cheap enough to fit on its own. This keeps the priority order
//      honest: a lower-priority item never jumps ahead of a higher-priority
//      one just because it happens to be cheaper.
export function recommendRestock(forecasts, budget) {
  const candidates = forecasts
    .filter(isRestockable)
    .slice()
    .sort((a, b) => {
      const rankDiff = TREND_RANK[a.trend] - TREND_RANK[b.trend]
      if (rankDiff !== 0) return rankDiff

      const growthA = a.forecasted_demand - a.current_demand
      const growthB = b.forecasted_demand - b.current_demand
      if (growthA !== growthB) return growthB - growthA // larger growth first

      return a.item_sku.localeCompare(b.item_sku)
    })

  const lines = []
  // Only budget-excluded candidates go here - forecasts filtered out above
  // by isRestockable() (no price, or zero demand) are never counted as
  // "excluded", since they were never restockable in the first place.
  const excluded = []
  let remaining = roundCents(budget)
  let stopped = false

  for (const forecast of candidates) {
    if (stopped) {
      excluded.push(forecast)
      continue
    }

    const fullQuantity = forecast.forecasted_demand
    const fullCost = roundCents(fullQuantity * forecast.unit_cost)

    if (fullCost <= remaining) {
      // Whole line fits within what's left of the budget.
      lines.push({
        item_sku: forecast.item_sku,
        item_name: forecast.item_name,
        trend: forecast.trend,
        quantity: fullQuantity,
        unit_cost: forecast.unit_cost,
        line_total: fullCost,
        lead_time_days: forecast.lead_time_days,
        partial: false
      })
      remaining = roundCents(remaining - fullCost)
    } else {
      // Doesn't fully fit - take as many whole units as remaining budget
      // allows, then stop (see rule above).
      const partialQuantity = Math.floor(remaining / forecast.unit_cost)
      if (partialQuantity >= 1) {
        const partialCost = roundCents(partialQuantity * forecast.unit_cost)
        lines.push({
          item_sku: forecast.item_sku,
          item_name: forecast.item_name,
          trend: forecast.trend,
          quantity: partialQuantity,
          unit_cost: forecast.unit_cost,
          line_total: partialCost,
          lead_time_days: forecast.lead_time_days,
          partial: true
        })
        remaining = roundCents(remaining - partialCost)
      } else {
        excluded.push(forecast)
      }
      stopped = true
    }
  }

  const total = roundCents(lines.reduce((sum, l) => sum + l.line_total, 0))

  return { lines, total, remaining, excluded }
}
