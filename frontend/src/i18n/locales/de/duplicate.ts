import type { MessageSchema } from '../en'

const duplicate: MessageSchema['duplicate'] = {
  action: 'Duplizieren',
  title: 'Termin duplizieren',
  calendar: 'Kalender',
  date: 'Datum',
  time: 'Uhrzeit',
  inviteParticipants: 'Teilnehmende zur Kopie einladen',
  inviteHint: 'Alle erhalten eine Einladung.',
  hint: 'Kopiert den Termin, wie er zuletzt gespeichert wurde, mit seinen Anhängen und den eigenen Erinnerungen.',
  seriesHint: 'Kopiert die ganze Serie ab diesem Datum; ihre geänderten und gelöschten Termine bleiben beim Original.',
  otherCalendarHint: 'Ressourcen bleiben zurück; eine gleichnamige Kategorie tritt an die Stelle der des Termins.',
  submit: 'Duplizieren',
  done: 'Termin dupliziert',
  noCalendar: 'Es gibt keinen Kalender, in den Termine hinzugefügt werden dürfen.',
}

export default duplicate
