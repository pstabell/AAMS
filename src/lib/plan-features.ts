import { PLANS, type PlanKey } from './stripe';

/**
 * Check if a user's plan includes a specific feature.
 * Use this on the client or server to gate UI and API access.
 */
export function planHasFeature(
  planKey: string | null | undefined,
  feature: 'ai' | 'emailForwarding' | 'multiUser' | 'floor2'
): boolean {
  const plan = PLANS[(planKey || 'starter') as PlanKey] || PLANS.starter;

  switch (feature) {
    case 'ai':
      return plan.aiEnabled;
    case 'emailForwarding':
      return plan.emailForwarding;
    case 'multiUser':
      return plan.multiUser;
    case 'floor2':
      return plan.floor === 'both';
    default:
      return false;
  }
}

/**
 * Get plan display info for UI.
 */
export function getPlanInfo(planKey: string | null | undefined) {
  const key = (planKey || 'starter') as PlanKey;
  const plan = PLANS[key] || PLANS.starter;
  return {
    key,
    name: plan.name,
    monthlyPrice: plan.monthlyPrice,
    aiEnabled: plan.aiEnabled,
    aiActionsPerDay: plan.aiActionsPerDay,
    emailForwarding: plan.emailForwarding,
    multiUser: plan.multiUser,
    floor: plan.floor,
    description: plan.description,
  };
}

/**
 * Get the suggested upgrade plan for a feature the user doesn't have.
 */
export function suggestUpgrade(
  currentPlan: string | null | undefined,
  missingFeature: 'ai' | 'emailForwarding' | 'multiUser' | 'floor2'
): { planKey: PlanKey; name: string; price: number } | null {
  const upgradePaths: Record<string, Record<string, PlanKey>> = {
    starter: { ai: 'pro', emailForwarding: 'autopilot', multiUser: 'agency_self', floor2: 'agency_self' },
    pro: { emailForwarding: 'autopilot', multiUser: 'agency_self', floor2: 'agency_self' },
    autopilot: { multiUser: 'agency_self', floor2: 'agency_self' },
    agency_self: { ai: 'agency_ai', emailForwarding: 'agency_ai' },
  };

  const current = currentPlan || 'starter';
  const suggested = upgradePaths[current]?.[missingFeature];
  if (!suggested) return null;

  const plan = PLANS[suggested];
  return { planKey: suggested, name: plan.name, price: plan.monthlyPrice };
}
