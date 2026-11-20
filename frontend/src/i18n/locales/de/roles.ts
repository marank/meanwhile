import type { MessageSchema } from '../en'

const roles: MessageSchema['roles'] = {
  read: 'Lesend',
  own: 'Eigene Termine',
  full: 'Alle Termine',
  manage: 'Verwalten',
  owner: 'Eigentümer',
  readDescription: 'Kann Termine ansehen.',
  ownDescription: 'Kann Termine erstellen, aber nur eigene bearbeiten.',
  fullDescription: 'Kann alle Termine erstellen und bearbeiten.',
  manageDescription: 'Kann außerdem Einstellungen und Zugriff ändern, aber den Kalender nicht löschen.',
  ownerDescription: 'Alle Rechte, auch den Kalender löschen.',
}

export default roles
