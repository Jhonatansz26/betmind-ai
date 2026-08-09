import { HomePage } from '@/components/betmind/home-page'
import { OnboardingGate } from '@/components/betmind/onboarding'

export default function Page() {
  return (
    <OnboardingGate>
      <HomePage />
    </OnboardingGate>
  )
}
