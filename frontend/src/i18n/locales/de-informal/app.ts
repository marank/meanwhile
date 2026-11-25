import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const app: Overlay<MessageSchema['app']> = {
  accountGeneralDescription: 'Dein Name, deine Sprache, dein Farbschema und deine Datumsformate.',
  publicCalendarsHint: 'Öffentliche Kalender erscheinen in deiner Seitenleiste, sobald du sie hinzufügst.',
  calendarNamePrompt: 'Gib einen Namen für den neuen Kalender ein.',
  folderNamePrompt: 'Gib einen Namen für den neuen Ordner ein.',
  feedUrlHelp:
    'Abonniere eine schreibgeschützte Version dieses Kalenders. Diese URL gehört nur dir und funktioniert nicht mehr, sobald du keinen Zugriff auf den Kalender mehr hast; behandle sie vertraulich.',
  caldavUrlHelp:
    'Verwende diese Adresse, um den Kalender mit einer CalDAV-kompatiblen App zu verbinden und zu synchronisieren. Melde dich dort mit deiner E-Mail-Adresse und einem App-Passwort an.',
  inviteUserText:
    '{name} bekommt eine E-Mail an {email} mit einem Link zur Anmeldung. Das Passwort steht nicht darin, das gibst du selbst weiter.',
  appPasswordsDescription:
    'CalDAV-Clients (Thunderbird, iPhone, …) melden sich mit deiner E-Mail-Adresse und einem App-Passwort an; dein Kontopasswort gilt nur hier in der Web-App.',
  appPasswordCreatedInfo: 'Dein neues App-Passwort lautet:',
  rotateFeedText:
    'Deine Abonnements mit der aktuellen URL funktionieren anschließend nicht mehr. Andere Mitglieder behalten ihre eigenen URLs.',
}

export default app
