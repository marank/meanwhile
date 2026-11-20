import type { MessageSchema } from '../en'

const agenda: MessageSchema['agenda'] = {
  search: 'Termine durchsuchen…',
  clearSearch: 'Suche leeren',
  upcomingOnly: 'Nur anstehende',
  count: 'Keine Termine | 1 Termin | {count} Termine',
  empty: 'Keine Termine im {period}',
  noMatches: 'Keine Treffer für „{query}“',
  noUpcoming: 'Keine anstehenden Termine mehr im {period}',
  showAll: 'Alle anzeigen',
  from: 'ab {time}',
  until: 'bis {time}',
  dayOf: 'Tag {index}/{count}',
  now: 'Jetzt',
  recurring: 'Wiederkehrend',
  newEvent: 'Neuer Termin',
}

export default agenda
