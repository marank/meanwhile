import type { MessageSchema } from '../en'

const rsvp: MessageSchema['rsvp'] = {
  invitation: 'Einladung',
  from: 'Einladung von {name}',
  organizer: 'Organisation',
  showMap: 'Auf einer Karte zeigen',
  yourTimeZone: 'Zeiten in Ihrer Zeitzone ({zone})',
  participants: 'Teilnehmende ({count})',
  guest: 'Gast',
  you: 'Sie',
  invitedAs: 'Eingeladen als {email}',
  addToCalendar: 'Zum Kalender hinzufügen',
  yourAnswer: 'Ihre Antwort',
  notSaved: 'noch nicht gespeichert',
  cancelled: 'Dieser Termin wurde abgesagt.',
  notFound: 'Diese Einladung gibt es nicht mehr. Sie wurde vielleicht zurückgezogen.',
  repeats: 'Wiederholt sich',
}

export default rsvp
