import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const auth: Overlay<MessageSchema['auth']> = {
  inviteTitle: 'Wähle dein Passwort',
  resetRequestHelp:
    'Gib deine E-Mail-Adresse ein. Gehört sie zu einem Konto, schicken wir dir einen Link, mit dem du ein neues Passwort festlegst.',
  resetSent:
    'Gehört die Adresse zu einem Konto, ist ein Link für ein neues Passwort unterwegs. Sieh in deinem Postfach nach.',
  resetDone: 'Dein Passwort wurde geändert. Du kannst dich jetzt damit anmelden.',
  resetInvalid: 'Dieser Link ist ungültig, schon benutzt oder abgelaufen. Fordere einen neuen an.',
}

export default auth
