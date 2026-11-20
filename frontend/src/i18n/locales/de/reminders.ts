import type { MessageSchema } from '../en'

const reminders: MessageSchema['reminders'] = {
  title: 'Erinnerungen',
  hint: 'Erinnerungen gelten nur für Sie, bei Serien für jeden Termin.',
  add: 'Erinnerung hinzufügen',
  quick: 'Schnellauswahl',
  before: 'vorher',
  amountLabel: 'Anzahl',
  unitLabel: 'Einheit',
  daysLabel: 'Tage vorher',
  daysBeforeAtInput: 'Tage vorher um',
  unit: { minutes: 'Minute | Minuten', hours: 'Stunde | Stunden', days: 'Tag | Tage', weeks: 'Woche | Wochen' },
  invalid: 'Bitte eine Zeit zwischen dem Beginn und {weeks} Wochen vorher wählen.',
  invalidAllDay: 'Bitte einen Zeitpunkt vor Beginn des Tages wählen, höchstens {weeks} Wochen vorher.',
  duplicate: 'Diese Erinnerung gibt es bereits.',
  remove: 'Erinnerung entfernen',
  none: 'Keine Erinnerungen',
  atStart: 'Zu Beginn',
  minutesBefore: '{n} Minute vorher | {n} Minuten vorher',
  hoursBefore: '{n} Stunde vorher | {n} Stunden vorher',
  daysBefore: '{n} Tag vorher | {n} Tage vorher',
  weeksBefore: '{n} Woche vorher | {n} Wochen vorher',
  onTheDay: 'Am Tag um 00:00',
  dayBeforeAt: 'Am Vortag um {time}',
  daysBeforeAt: '{n} Tage vorher um {time}',
  due: 'Erinnerung: „{title}“ beginnt {when}',
  untitled: 'Ohne Titel',
}

export default reminders
