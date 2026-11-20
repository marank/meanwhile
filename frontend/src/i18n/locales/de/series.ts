import type { MessageSchema } from '../en'

const series: MessageSchema['series'] = {
  editTitle: 'Wiederkehrenden Termin ändern',
  editMessage: 'Für welche Termine der Serie soll die Änderung gelten?',
  deleteTitle: 'Wiederkehrenden Termin löschen',
  deleteMessage: 'Welche Termine der Serie sollen gelöscht werden?',
  this: 'Nur diesen Termin',
  following: 'Diesen und alle folgenden Termine',
  all: 'Alle Termine der Serie',
  exceptionHint: 'Dieser Termin wurde abweichend von seiner Serie geändert.',
  deleteExceptionText: 'Der Termin wird aus der Serie entfernt.',
}

export default series
