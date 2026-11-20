import type { MessageSchema } from '../en'

const booking: MessageSchema['booking'] = {
  awaiting: 'Wartet noch auf Genehmigung für: {names}',
  pending: 'Wartet auf Genehmigung',
  pendingHint: 'Bis zur Genehmigung sehen nur Ersteller, Teilnehmende und Genehmiger diese Buchung.',
  approved: 'Genehmigt',
  rejected: 'Abgelehnt',
  cancelled: 'Storniert',
  notePlaceholder: 'Notiz (optional)',
  approve: 'Genehmigen',
  reject: 'Ablehnen',
  conflict: 'Dieser Zeitraum ist für diese Ressource bereits gebucht.',
}

export default booking
