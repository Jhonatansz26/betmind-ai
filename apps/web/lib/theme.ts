export type ThemePreference = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'betmind_theme'
const COOKIE_KEY = 'betmind_theme'

export function getStoredTheme(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
}

export function setStoredTheme(theme: ThemePreference) {
  localStorage.setItem(STORAGE_KEY, theme)
  document.cookie = `${COOKIE_KEY}=${theme}; path=/; max-age=31536000; SameSite=Lax`
}

export function resolveIsDark(theme: ThemePreference): boolean {
  if (theme === 'dark') return true
  if (theme === 'light') return false
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyTheme(theme: ThemePreference) {
  const isDark = resolveIsDark(theme)
  document.documentElement.classList.toggle('dark', isDark)
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
}
