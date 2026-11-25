import type { MessageSchema } from '../en'

const availability: MessageSchema['availability'] = {
  title: 'Verfügbarkeit',
  hint: 'Zeigt nur, wann jemand belegt ist, keine Termindetails.',
  me: 'Ich',
  previousDay: 'Vorheriger Tag',
  nextDay: 'Nächster Tag',
  busy: 'Belegt',
  tentative: 'Vorläufig belegt',
  outOfOffice: 'Abwesend',
  thisEvent: 'Dieser Termin',
  allFree: 'Alle sind zu dieser Zeit frei.',
  conflicts: 'Zu dieser Zeit belegt: {names}',
  noOne: 'Fügen Sie Teilnehmende oder eine Ressource hinzu, um deren Verfügbarkeit zu sehen.',
}

export default availability
