import type { MessageSchema } from '../en'

const attachments: MessageSchema['attachments'] = {
  title: 'Anhänge',
  none: 'Noch keine Anhänge.',
  addFiles: 'Dateien hinzufügen',
  linkUrl: 'Link',
  linkUrlPlaceholder: 'https://…',
  linkName: 'Titel (optional)',
  addLink: 'Link hinzufügen',
  invalidUrl: 'Eine Adresse eingeben, die mit http:// oder https:// beginnt.',
  pending: 'wird beim Speichern hinzugefügt',
  remove: 'Entfernen',
  removeNamed: '{name} entfernen',
  addedBy: 'Hinzugefügt von {name}',
  hint: 'PDFs, Bilder, Office-Dokumente, Text- und ZIP-Dateien; sie bleiben beim Termin gespeichert.',
}

export default attachments
