import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const unsubscribe: Overlay<MessageSchema['unsubscribe']> = {
  doneEvent: '{email} bekommt keine E-Mails mehr zum Termin „{title}“. In der App siehst du weiterhin, was passiert.',
  undoHint: 'In deinen E-Mail-Einstellungen kannst du sie wieder einschalten und die anderen Arten wählen.',
  undoHintEvent: 'Versehentlich geklickt? Hier kannst du es rückgängig machen.',
  invalid: 'Dieser Link ist nicht gültig. Welche E-Mails du bekommst, wählst du in deinen E-Mail-Einstellungen.',
}

export default unsubscribe
