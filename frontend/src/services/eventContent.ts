import type { EventDisplayInfo } from '@fullcalendar/vue3'
import type { Occurrence } from '@/api'
import { formatTime } from './datetime'
import { DAY_MS } from './days'
import { resourceIconSvg } from './resourceIcons'

export interface LabelPart {
  text: string
  /** Name of the icon of the place or resource this part names. */
  icon?: string
}

// What an event says: its title, then where (the place) and with what (the resource), each with its icon.
export function eventParts(occ: Occurrence, t: (key: string) => string): LabelPart[] {
  let title = occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
  if (occ.status === 'rejected' || occ.status === 'cancelled') {
    title = `${title} (${t('event.declined')})`
  } else if (occ.status === 'pending') {
    title = `${title} (${t('event.pending')})`
  }
  return [
    { text: title },
    { text: occ.location, icon: occ.location_resource_id ? occ.location_resource_icon : undefined },
    { text: occ.resource_name ?? '', icon: occ.resource_icon },
  ].filter((part) => part.text)
}

export function eventLabel(parts: LabelPart[]): string {
  return parts.map((part) => part.text).join(' · ')
}

/** FullCalendar's `eventContent`: the time, the category marker and the parts with their icons. */
export function renderEventContent(info: EventDisplayInfo) {
  const content = document.createElement('span')
  const duration = info.event.start && info.event.end ? info.event.end.getTime() - info.event.start.getTime() : 0
  const classes = [duration > DAY_MS ? 'fc-event-label fc-event-label-multiday' : 'fc-event-label']
  // In the week's narrow columns the time goes above the title, which wraps; short events stay on one line.
  const stacked = info.view.type === 'timeGridWeek' && !info.event.allDay && !info.isShort
  if (stacked) classes.push('fc-event-label-stacked')
  const status = info.event.extendedProps.status as string | undefined
  if (status === 'rejected' || status === 'cancelled') {
    classes.push('fc-event-declined')
  }
  content.className = classes.join(' ')
  if (info.timeText) {
    const time = document.createElement('span')
    time.className = 'fc-event-time-label'
    if (stacked && info.event.start && info.event.end) {
      // Stacked, the start and the end each get a line of their own.
      time.textContent = formatTime(info.event.start)
      const end = document.createElement('span')
      end.className = 'fc-event-time-label fc-event-end-label'
      end.textContent = formatTime(info.event.end)
      content.append(time, end)
    } else {
      time.textContent = info.timeText
      content.append(time)
    }
  }
  const parts = info.event.extendedProps.parts as LabelPart[]
  const text = document.createElement('span')
  const categoryColor = info.event.extendedProps.categoryColor as string | null
  if (categoryColor) {
    const marker = document.createElement('span')
    marker.className = 'fc-event-category-marker'
    marker.style.backgroundColor = categoryColor
    // Stacked, it starts the title's first line rather than taking a line of its own.
    if (stacked) text.append(marker)
    else content.append(marker)
  }
  content.append(text)
  parts.forEach((part, index) => {
    if (index > 0) text.append(' · ')
    const svg = resourceIconSvg(part.icon, 12)
    if (svg) {
      const icon = document.createElement('span')
      icon.className = 'fc-event-resource-icon'
      icon.innerHTML = svg
      text.append(icon)
    }
    text.append(part.text)
  })
  return { domNodes: [content] }
}
