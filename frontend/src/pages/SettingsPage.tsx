import { useEffect, useState, type FormEvent } from 'react'
import { Link, useBlocker } from 'react-router-dom'
import { useSettings, useUpdateSettings, useChangePassword } from '../api/hooks'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'
import type { JournalDateFormat, JournalTimeFormat } from '../api/types'

// P1.1A: option label shows the rendered example (matching the exact
// backend output for 2026-08-29 -- see services.format_journal_date), never
// the raw format id -- users shouldn't have to interpret "day_long_month_year".
const JOURNAL_DATE_FORMAT_OPTIONS: { value: JournalDateFormat; label: string }[] = [
  { value: 'long_month_day_year', label: 'August 29, 2026' },
  { value: 'short_month_day_year', label: 'Aug 29, 2026' },
  { value: 'day_long_month_year', label: '29 August 2026' },
  { value: 'day_short_month_year', label: '29 Aug 2026' },
  { value: 'us_numeric', label: '08/29/2026' },
  { value: 'day_first_numeric', label: '29/08/2026' },
  { value: 'iso', label: '2026-08-29' },
  { value: 'weekday_long', label: 'Saturday, August 29, 2026' },
]

const JOURNAL_TIME_FORMAT_OPTIONS: { value: JournalTimeFormat; label: string }[] = [
  { value: '12_hour', label: '10:42 AM' },
  { value: '24_hour', label: '22:42' },
]

const DEFAULTS = {
  darkMode: false,
  sidebarColor: '#f0f0f0',
  textColor: '#000000',
  bgColor: '#ffffff',
  toolbarColor: '#dddddd',
  editorColor: '#ffffff',
  darkSidebarColor: '#333333',
  darkTextColor: '#eeeeee',
  darkBgColor: '#222222',
  darkToolbarColor: '#555555',
  darkEditorColor: '#444444',
}

const COLOR_SETTINGS = [
  ['sidebarColor', 'darkSidebarColor', 'Sidebar', 'Navigation and account area'],
  ['textColor', 'darkTextColor', 'Text', 'Primary text throughout the app'],
  ['bgColor', 'darkBgColor', 'Background', 'Main page background'],
  ['toolbarColor', 'darkToolbarColor', 'Toolbar', 'Chapter formatting toolbar'],
  ['editorColor', 'darkEditorColor', 'Editor', 'Writing page and content panels'],
] as const

const APPEARANCE_KEYS = Object.keys(DEFAULTS) as Array<keyof typeof DEFAULTS>

function getSavedAppearance(settings: NonNullable<ReturnType<typeof useSettings>['data']>) {
  return {
    darkMode: settings.darkMode,
    sidebarColor: settings.sidebarColor,
    textColor: settings.textColor,
    bgColor: settings.bgColor,
    toolbarColor: settings.toolbarColor,
    editorColor: settings.editorColor,
    darkSidebarColor: settings.darkSidebarColor ?? DEFAULTS.darkSidebarColor,
    darkTextColor: settings.darkTextColor ?? DEFAULTS.darkTextColor,
    darkBgColor: settings.darkBgColor ?? DEFAULTS.darkBgColor,
    darkToolbarColor: settings.darkToolbarColor ?? DEFAULTS.darkToolbarColor,
    darkEditorColor: settings.darkEditorColor ?? DEFAULTS.darkEditorColor,
  }
}

function getPreviewColors(form: typeof DEFAULTS) {
  return form.darkMode
    ? {
        '--sidebar-bg': form.darkSidebarColor,
        '--text-color': form.darkTextColor,
        '--bg-color': form.darkBgColor,
        '--toolbar-bg': form.darkToolbarColor,
        '--editor-bg': form.darkEditorColor,
      }
    : {
        '--sidebar-bg': form.sidebarColor,
        '--text-color': form.textColor,
        '--bg-color': form.bgColor,
        '--toolbar-bg': form.toolbarColor,
        '--editor-bg': form.editorColor,
      }
}

export default function SettingsPage() {
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const [form, setForm] = useState(DEFAULTS)
  const [appearanceMessage, setAppearanceMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const savedAppearance = settings ? getSavedAppearance(settings) : DEFAULTS
  const hasUnsavedAppearance = Boolean(
    settings && APPEARANCE_KEYS.some((key) => form[key] !== savedAppearance[key]),
  )
  const blocker = useBlocker(hasUnsavedAppearance)

  useEffect(() => {
    if (settings) {
      setForm(getSavedAppearance(settings))
    }
  }, [settings])

  // Preview appearance variables on the Settings content area only. The
  // saved body-level theme remains untouched until the user explicitly saves.
  useEffect(() => {
    const main = document.getElementById('main')
    if (!main) return
    const colors = getPreviewColors(form)
    for (const [property, value] of Object.entries(colors)) {
      main.style.setProperty(property, value)
    }
    main.style.backgroundColor = 'var(--bg-color)'
    main.style.color = 'var(--text-color)'
    main.classList.toggle('settings-preview-dark', form.darkMode)

    return () => {
      for (const property of Object.keys(colors)) main.style.removeProperty(property)
      main.style.removeProperty('background-color')
      main.style.removeProperty('color')
      main.classList.remove('settings-preview-dark')
    }
  }, [form])

  useEffect(() => {
    if (!hasUnsavedAppearance) return
    function warnBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [hasUnsavedAppearance])

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setAppearanceMessage(null)
    try {
      await update.mutateAsync(form)
      setAppearanceMessage({ type: 'success', text: 'Appearance settings saved.' })
    } catch (err) {
      setAppearanceMessage({
        type: 'error',
        text: err instanceof ApiError ? err.message : 'Failed to save settings',
      })
    }
  }

  function handleReset() {
    setForm(DEFAULTS)
    setAppearanceMessage({ type: 'success', text: 'Defaults previewed. Save appearance to apply them.' })
  }

  async function saveAndLeave() {
    setAppearanceMessage(null)
    try {
      await update.mutateAsync(form)
      if (blocker.state === 'blocked') blocker.proceed()
    } catch (err) {
      setAppearanceMessage({
        type: 'error',
        text: err instanceof ApiError ? err.message : 'Failed to save settings',
      })
    }
  }

  return (
    <div className="settings-page">
      <header className="settings-page-header">
        <div className="settings-eyebrow">Preferences</div>
        <h1>Settings</h1>
        <p>Personalize your workspace and manage your account.</p>
      </header>

      <div className="settings-layout">
        <div className="settings-column">
          <section className="settings-panel appearance-panel">
            <div className="settings-panel-header">
              <div>
                <h2>Appearance</h2>
                <p>Choose how CalWriter looks for your account.</p>
              </div>
            </div>

            <form onSubmit={handleSave}>
              <label className="setting-toggle-row">
                <span>
                  <strong>Color mode</strong>
                  <small>Switch between your separately saved light and dark palettes.</small>
                </span>
                <span className="setting-mode-switch">
                  <span className={!form.darkMode ? 'active' : undefined}>Light</span>
                  <span className="setting-switch">
                    <input
                      type="checkbox"
                      checked={form.darkMode}
                      onChange={(e) => setForm({ ...form, darkMode: e.target.checked })}
                      aria-label="Use dark mode"
                    />
                    <span className="setting-switch-track" aria-hidden="true" />
                  </span>
                  <span className={form.darkMode ? 'active' : undefined}>Dark</span>
                </span>
              </label>

              <div className="appearance-preview" aria-label="Appearance preview">
                <div className="appearance-preview-label">Live preview</div>
                <div className="appearance-preview-window">
                  <div className="appearance-preview-sidebar">
                    <span className="appearance-preview-brand" />
                    <span />
                    <span />
                    <span className="short" />
                  </div>
                  <div className="appearance-preview-main">
                    <div className="appearance-preview-toolbar">
                      <span />
                      <span />
                      <span />
                    </div>
                    <div className="appearance-preview-editor">
                      <strong>Chapter preview</strong>
                      <span />
                      <span />
                      <span className="short" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="palette-heading">
                <strong>{form.darkMode ? 'Dark' : 'Light'} palette</strong>
                <small>Each mode keeps its own custom colors.</small>
              </div>
              <div className="color-settings-grid">
                {COLOR_SETTINGS.map(([lightKey, darkKey, label, description]) => {
                  const key = form.darkMode ? darkKey : lightKey
                  return (
                    <label className="color-setting" key={lightKey}>
                      <span className="color-setting-copy">
                        <strong>{label}</strong>
                        <small>{description}</small>
                      </span>
                      <span className="color-setting-control">
                        <input
                          type="color"
                          value={form[key]}
                          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                          aria-label={`${label} color`}
                        />
                        <code>{(form[key] ?? DEFAULTS[key]).toUpperCase()}</code>
                      </span>
                    </label>
                  )
                })}
              </div>

              {appearanceMessage && (
                <div className={`settings-message ${appearanceMessage.type}`} role="status">
                  {appearanceMessage.text}
                </div>
              )}

              <div className="settings-form-actions">
                <button className="settings-primary-action" type="submit" disabled={update.isPending}>
                  {update.isPending ? 'Saving…' : 'Save appearance'}
                </button>
                <button className="settings-secondary-action" type="button" onClick={handleReset} disabled={update.isPending}>
                  Restore defaults
                </button>
              </div>
            </form>
          </section>

          <EditorStatsPanel />
          <JournalFormattingPanel />
        </div>

        <div className="settings-column">
          <AccountPanel />
          <TimezonePanel />
          <ChangePasswordForm />
        </div>
      </div>

      {blocker.state === 'blocked' && (
        <div className="settings-leave-overlay" role="presentation">
          <div className="settings-leave-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-leave-title">
            <h2 id="settings-leave-title">Apply appearance changes?</h2>
            <p>You have preview changes that have not been saved to your account.</p>
            {appearanceMessage?.type === 'error' && (
              <div className="settings-message error" role="alert">{appearanceMessage.text}</div>
            )}
            <div className="settings-leave-actions">
              <button type="button" className="settings-primary-action" onClick={saveAndLeave} disabled={update.isPending} autoFocus>
                {update.isPending ? 'Applying…' : 'Apply and leave'}
              </button>
              <button type="button" className="settings-secondary-action" onClick={() => blocker.proceed()} disabled={update.isPending}>
                Leave without saving
              </button>
              <button type="button" className="settings-dialog-cancel" onClick={() => blocker.reset()} disabled={update.isPending}>
                Stay here
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EditorStatsPanel() {
  const { data: settings } = useSettings()
  const update = useUpdateSettings()

  if (!settings) return null

  return (
    <section className="settings-panel editor-stats-panel">
      <div className="settings-panel-header">
        <div>
          <h2>Editor stats</h2>
          <p>Choose which personal writing details appear in every chapter footer.</p>
        </div>
      </div>
      <label className="setting-toggle-row">
        <span>
          <strong>Show word count</strong>
          <small>Display the chapter’s current total words.</small>
        </span>
        <span className="setting-switch">
          <input
            type="checkbox"
            checked={settings.showWordCount}
            onChange={(e) => update.mutate({ showWordCount: e.target.checked })}
            aria-label="Show word count"
          />
          <span className="setting-switch-track" aria-hidden="true" />
        </span>
      </label>
      <label className="setting-toggle-row">
        <span>
          <strong>Show average WPM</strong>
          <small>Display your typed words per active writing minute. Requires word count.</small>
        </span>
        <span className="setting-switch">
          <input
            type="checkbox"
            checked={settings.showAverageWpm}
            disabled={!settings.showWordCount}
            onChange={(e) => update.mutate({ showAverageWpm: e.target.checked })}
            aria-label="Show average WPM"
          />
          <span className="setting-switch-track" aria-hidden="true" />
        </span>
      </label>
    </section>
  )
}

// P1.1A. A shared Journal always uses the *Book owner's* saved preferences
// here (never the requesting Editor's) -- same authoritative-owner rule as
// timezone (see TimezonePanel) -- so this panel only ever affects Journals
// this account owns.
function JournalFormattingPanel() {
  const { data: settings } = useSettings()
  const update = useUpdateSettings()

  if (!settings) return null

  return (
    <section className="settings-panel journal-formatting-panel">
      <div className="settings-panel-header">
        <div>
          <h2>Journal</h2>
          <p>
            These formats are used for newly created Journal entries and timestamps. Existing Journal names and text
            are not changed.
          </p>
        </div>
      </div>
      <label className="journal-format-select">
        <span>Journal date format</span>
        <select
          value={settings.journalDateFormat}
          onChange={(e) => update.mutate({ journalDateFormat: e.target.value as JournalDateFormat })}
        >
          {JOURNAL_DATE_FORMAT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
      <label className="journal-format-select">
        <span>Journal time format</span>
        <select
          value={settings.journalTimeFormat}
          onChange={(e) => update.mutate({ journalTimeFormat: e.target.value as JournalTimeFormat })}
        >
          {JOURNAL_TIME_FORMAT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    </section>
  )
}

function TimezonePanel() {
  const { user, updateTimezone } = useAuth()
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  const [timezoneDraft, setTimezoneDraft] = useState<string | null>(null)
  const timezone = timezoneDraft ?? user?.timezone ?? browserTimezone
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const timezones = typeof Intl.supportedValuesOf === 'function'
    ? ['UTC', ...Intl.supportedValuesOf('timeZone').filter((zone) => zone !== 'UTC')]
    : ['UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles']

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      await updateTimezone(timezone.trim())
      setTimezoneDraft(null)
      setMessage({ type: 'success', text: 'Timezone updated.' })
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof ApiError ? err.message : 'Failed to update timezone',
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="settings-panel timezone-panel">
      <div className="settings-panel-header">
        <div>
          <h2>Timezone</h2>
          <p>Calendar days, goals, streaks, and writing hours use this IANA timezone.</p>
        </div>
      </div>
      <form className="password-form" onSubmit={handleSubmit}>
        <label>
          <span>Timezone</span>
          <input
            type="text"
            list="calwriter-timezones"
            value={timezone}
            onChange={(e) => {
              setTimezoneDraft(e.target.value)
              setMessage(null)
            }}
            placeholder="America/New_York"
            autoComplete="off"
            required
          />
          <small>Browser detected: {browserTimezone}</small>
        </label>
        <datalist id="calwriter-timezones">
          {timezones.map((zone) => <option key={zone} value={zone} />)}
        </datalist>
        {message && <div className={`settings-message ${message.type}`} role="status">{message.text}</div>}
        <div className="settings-form-actions">
          <button
            className="settings-primary-action"
            type="submit"
            disabled={saving || !timezone.trim() || timezone.trim() === user?.timezone}
          >
            {saving ? 'Saving…' : 'Save timezone'}
          </button>
        </div>
      </form>
    </section>
  )
}

function AccountPanel() {
  const { user } = useAuth()

  return (
    <section className="settings-panel account-panel">
      <div className="settings-panel-header">
        <div>
          <h2>Account</h2>
          <p>Your login and account type.</p>
        </div>
      </div>
      <dl className="account-info">
        <div className="account-info-row">
          <dt>Username</dt>
          <dd>{user?.username}</dd>
        </div>
        <div className="account-info-row">
          <dt>Account type</dt>
          <dd>
            <span className={`account-type-badge${user?.isAdmin ? ' admin' : ''}`}>
              {user?.isAdmin ? 'Admin' : 'Standard'}
            </span>
          </dd>
        </div>
      </dl>
      {user?.isAdmin && (
        <div className="account-panel-actions">
          <Link className="folder-action" to="/settings/invite">
            Invite a user
          </Link>
        </div>
      )}
    </section>
  )
}

function ChangePasswordForm() {
  const changePassword = useChangePassword()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match')
      return
    }
    try {
      await changePassword.mutateAsync({ currentPassword, newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setSuccess(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to change password')
    }
  }

  return (
    <section className="settings-panel password-panel">
      <div className="settings-panel-header">
        <div>
          <h2>Change password</h2>
          <p>Use at least eight characters for your new password.</p>
        </div>
      </div>
      <form className="password-form" onSubmit={handleSubmit}>
        <label>
          <span>Current password</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          <span>New password</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <label>
          <span>Confirm new password</span>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>

        {success && <div className="settings-message success" role="status">Password updated.</div>}
        {error && <div className="settings-message error" role="alert">{error}</div>}

        <div className="settings-form-actions">
          <button className="settings-primary-action" type="submit" disabled={changePassword.isPending}>
            {changePassword.isPending ? 'Updating…' : 'Update password'}
          </button>
        </div>
      </form>
    </section>
  )
}
