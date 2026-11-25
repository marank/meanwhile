import type { MessageSchema } from '../en'

const auth: MessageSchema['auth'] = {
  login: 'Anmelden',
  register: 'Registrieren',
  email: 'E-Mail',
  password: 'Passwort',
  showPassword: 'Passwort anzeigen',
  hidePassword: 'Passwort ausblenden',
  displayName: 'Anzeigename',
  noAccount: 'Noch kein Konto? Registrieren',
  hasAccount: 'Bereits ein Konto? Anmelden',
  forgotPassword: 'Passwort vergessen?',
  resetTitle: 'Passwort zurücksetzen',
  inviteTitle: 'Wählen Sie Ihr Passwort',
  resetRequestHelp:
    'Geben Sie Ihre E-Mail-Adresse ein. Gehört sie zu einem Konto, schicken wir Ihnen einen Link, mit dem Sie ein neues Passwort festlegen.',
  resetSend: 'Link senden',
  resetSent:
    'Gehört die Adresse zu einem Konto, ist ein Link für ein neues Passwort unterwegs. Sehen Sie in Ihrem Postfach nach.',
  newPassword: 'Neues Passwort',
  currentPassword: 'Aktuelles Passwort',
  setPassword: 'Passwort setzen',
  resetDone: 'Ihr Passwort wurde geändert. Sie können sich jetzt damit anmelden.',
  resetInvalid: 'Dieser Link ist ungültig, schon benutzt oder abgelaufen. Fordern Sie einen neuen an.',
  backToLogin: 'Zurück zur Anmeldung',
  changePassword: 'Passwort ändern',
  passwordChanged: 'Passwort geändert.',
  passwordChangeFailed: 'Das Passwort konnte nicht geändert werden.',
}

export default auth
