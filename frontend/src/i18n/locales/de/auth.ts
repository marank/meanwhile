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
  inviteTitle: 'Wähle dein Passwort',
  resetRequestHelp:
    'Gib deine E-Mail-Adresse ein. Gehört sie zu einem Konto, schicken wir dir einen Link, mit dem du ein neues Passwort setzt.',
  resetSend: 'Link senden',
  resetSent:
    'Gehört die Adresse zu einem Konto, ist ein Link für ein neues Passwort unterwegs. Sieh in deinem Postfach nach.',
  newPassword: 'Neues Passwort',
  currentPassword: 'Aktuelles Passwort',
  setPassword: 'Passwort setzen',
  resetDone: 'Dein Passwort wurde geändert. Du kannst dich jetzt damit anmelden.',
  resetInvalid: 'Dieser Link ist ungültig, schon benutzt oder abgelaufen. Fordere einen neuen an.',
  backToLogin: 'Zurück zur Anmeldung',
  changePassword: 'Passwort ändern',
  passwordChanged: 'Passwort geändert.',
  passwordChangeFailed: 'Das Passwort konnte nicht geändert werden.',
}

export default auth
