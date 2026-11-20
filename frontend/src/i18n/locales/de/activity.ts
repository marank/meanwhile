import type { MessageSchema } from '../en'

const activity: MessageSchema['activity'] = {
  created: '{name} hat diesen Termin erstellt',
  updated: '{name} hat {fields} geändert',
  updatedPending: '{name} hat {fields} geändert — erneute Genehmigung erforderlich',
  approved: '{name} hat diesen Termin genehmigt',
  approvedWithNote: '{name} hat genehmigt: {note}',
  rejected: '{name} hat diesen Termin abgelehnt',
  rejectedWithNote: '{name} hat abgelehnt: {note}',
  cancelled: '{name} hat diesen Termin storniert',
  occurrenceChanged: '{name} hat den Termin am {date} geändert',
  occurrenceDeleted: '{name} hat den Termin am {date} aus der Serie gelöscht',
  seriesEnded: '{name} hat die Serie ab {date} beendet',
  empty: 'Noch keine Aktivitäten.',
  comment: 'Kommentieren',
  commentPlaceholder: 'Kommentar schreiben…',
  field: {
    location: 'Veranstaltungsort',
    location_resource: 'gebuchten Veranstaltungsort',
    title: 'Titel',
    description: 'Beschreibung',
    start: 'Beginn',
    end: 'Ende',
    all_day: 'ganztägig',
    rrule: 'Wiederholung',
    category: 'Kategorie',
    resource: 'Ressource',
    show_recurrence_count: 'Wiederholungszähler',
  },
}

export default activity
