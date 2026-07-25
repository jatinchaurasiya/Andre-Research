"""Andre — shared monetisation model.

Every agent prompt that needs to be monetisation-aware appends this
constant to its system prompt. Keeping it in one place guarantees that
the entire pipeline (PMF research → Feature Architecture → PRD →
UI/UX → Marketing) reasons from the *same* business model.
"""
from __future__ import annotations


MONETISATION_MODEL = """\
## App Monetisation Model (Apply to ALL recommendations)

### Free Tier (Ad-Supported)
- Full core functionality available for free.
- Google AdMob ads — three types:
  BANNER:       shown on non-task screens (home feed, settings, results lists).
                Never on: onboarding, core task screens, error states.
                Position: bottom of screen, 50dp height standard.
  INTERSTITIAL: shown at natural session breaks only.
                Trigger points: after completing a task, when navigating
                back to home, after saving/sharing something.
                Frequency cap: MAX 1 per 8 minutes per session.
                Never: mid-task, during data entry, on first launch.
  REWARDED:     user voluntarily watches a ~30s video to unlock a premium
                feature for 24 hours (bridge between free and paid).
                Examples: unlock a premium export, remove ads for the
                session, unlock an advanced filter, extra AI queries.
                UX rule: a rewarded ad must ALWAYS feel like a gift, never
                a punishment. User initiates it, never auto-triggered.
- Core value proposition is NEVER blocked by ads.
- User can always complete their primary job-to-be-done on the free tier.

### Paid Tier (Subscription — Very Affordable)
Platform: RevenueCat SDK (free tier up to ~$2,500 MRR).
         Handles BOTH Google Play Billing AND Apple StoreKit 2
         in Kotlin Multiplatform with one unified API.

Pricing philosophy: price low enough that upgrading feels like a
no-brainer, not a decision. Target: "less than a coffee per month".

Default pricing (adjust based on competitor research):
  Monthly:  $1.99/month
  Annual:   $9.99/year  ($0.83/month — 58% saving)
  Trial:    7 days free on the annual plan only

Paid tier typically includes:
  - Complete ad removal (strongest upgrade motivator).
  - Unlimited usage (free tier has soft caps, not hard blocks).
  - The app's killer differentiator feature (from the Improvement Agent).
  - Cross-device sync (free = single device).
  - Any AI/smart features at full capacity (free = limited).
  - Export/share in premium formats.
  - Priority feature access (new features = paid first).

### Subscription Infrastructure (KMP)
Android: Google Play Billing Library 7.x (via RevenueCat).
iOS:     StoreKit 2 (via RevenueCat).
RevenueCat KMP SDK: `com.revenuecat.purchases:purchases-kmp`.
Free tier: $0 until app earns ~$2,500/month — perfect for launch.

### Upsell UX Rules (Non-negotiable)
- Paywall shown max ONCE per session unless the user taps "upgrade" themselves.
- Never block a user mid-task with a paywall.
- Show value BEFORE asking for money (let free users hit the cap naturally,
  then offer upgrade as the logical next step).
- Paywall must show: what they get, social proof, price, trial offer.
- No dark patterns: no countdown timers, no guilt copy, no fake X buttons.
- "Maybe later" always visible and functional.
"""
