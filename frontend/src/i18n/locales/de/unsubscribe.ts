import type { MessageSchema } from '../en'

const unsubscribe: MessageSchema['unsubscribe'] = {
  title: 'E-Mails abbestellen',
  question: 'Keine E-Mails mehr zu „{kind}“ an {email} senden?',
  confirm: 'Abbestellen',
  questionEvent: 'Keine E-Mails mehr zum Termin „{title}“ an {email} senden?',
  done: '{email} bekommt keine E-Mails mehr zu „{kind}“.',
  doneEvent: '{email} bekommt keine E-Mails mehr zum Termin „{title}“. In der App sehen Sie weiterhin, was passiert.',
  undoHint: 'In Ihren E-Mail-Einstellungen können Sie sie wieder einschalten und die anderen Arten wählen.',
  undoHintEvent: 'Versehentlich geklickt? Hier können Sie es rückgängig machen.',
  undo: 'Rückgängig machen',
  settings: 'E-Mail-Einstellungen',
  invalid: 'Dieser Link ist nicht gültig. Welche E-Mails Sie bekommen, wählen Sie in Ihren E-Mail-Einstellungen.',
}

export default unsubscribe
