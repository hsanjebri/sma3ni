# Store Release Checklist — Sma3ni

## Accounts
- [ ] Apple Developer Program ($99/year)
- [ ] Google Play Console ($25 one-time). New personal accounts must run a closed test (12+ testers, 14 days) before production; check current rules when you create it.

## Both stores
- [ ] App name without third-party trademarks ("Sma3ni – Voice notes to text"; never "WhatsApp" in the name or icon)
- [ ] Description mentions it works with audio shared from any app; "Not affiliated with WhatsApp or Meta"
- [ ] Privacy policy URL (AR/FR/EN)
- [ ] Support email + simple website / landing page
- [ ] Screenshots (Arabic + French), demo video
- [ ] Age rating questionnaire
- [ ] Content: transcripts may contain user content, so no public sharing feature in-app

## Apple
- [ ] Bundle id, App Group (`group.app.sma3ni`) for main app + Share Extension
- [ ] Privacy labels: "Audio Data — not collected/linked" (processed only), "Diagnostics" if Sentry
- [ ] Privacy manifest (`PrivacyInfo.xcprivacy`) for app + extension, required-reason APIs declared
- [ ] Review notes: how to test (attach a sample audio file in the notes or provide a test button), explain server processing and deletion
- [ ] TestFlight external testing (beta review)
- [ ] Encryption export compliance: standard HTTPS only

## Google Play
- [ ] Data Safety form matching `PRIVACY.md`
- [ ] Target latest required API level
- [ ] Closed testing track: 12+ testers for 14 days, collect feedback
- [ ] Signed AAB via EAS (`eas build -p android --profile production`)

## Pre-launch QA
- [ ] Share from WhatsApp, Telegram, Messenger, Files on both platforms
- [ ] Opus, m4a, aac, mp3 inputs
- [ ] 1 s, 30 s, 5 min, > 5 min (error) notes
- [ ] Offline / slow network / server down
- [ ] RTL layout, dark mode, large fonts
- [ ] Delete all actually deletes

## Post-launch
- [ ] Monitor crash rate (< 1%), latency, error codes
- [ ] Reply to reviews
- [ ] Release notes in AR/FR/EN
