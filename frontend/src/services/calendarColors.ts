export type CalendarPaletteColors = {
  calendar: string
  today: string
  weekend: string
}

export type CalendarColorPalette = {
  id: string
  name: {
    en: string
    de: string
  }
  light: CalendarPaletteColors
  dark: CalendarPaletteColors
}

export const calendarColorPalettes: CalendarColorPalette[] = [
  { id: 'blue', name: { en: 'Blue', de: 'Blau' }, light: { calendar: '#cbe0fe', today: '#80b3fe', weekend: '#bed1ed' }, dark: { calendar: '#15253d', today: '#2b528b', weekend: '#22334c' } },
  { id: 'sky', name: { en: 'Sky', de: 'Himmel' }, light: { calendar: '#c2e4f8', today: '#53bdf5', weekend: '#b7d4e7' }, dark: { calendar: '#0b2838', today: '#025a7e', weekend: '#1a3647' } },
  { id: 'cyan', name: { en: 'Cyan', de: 'Cyan' }, light: { calendar: '#c0e6ec', today: '#44c5d6', weekend: '#b5d6dc' }, dark: { calendar: '#072b2f', today: '#005e68', weekend: '#17393d' } },
  { id: 'teal', name: { en: 'Teal', de: 'Türkis' }, light: { calendar: '#c3e7e1', today: '#55c7ba', weekend: '#b8d7d2' }, dark: { calendar: '#0b2b28', today: '#036058', weekend: '#1a3935' } },
  { id: 'emerald', name: { en: 'Emerald', de: 'Smaragd' }, light: { calendar: '#c6e7d5', today: '#61c99a', weekend: '#bad8c8' }, dark: { calendar: '#0f2c1f', today: '#126143', weekend: '#1d3a2c' } },
  { id: 'green', name: { en: 'Green', de: 'Grün' }, light: { calendar: '#cae7cd', today: '#71c880', weekend: '#bdd8c0' }, dark: { calendar: '#142b18', today: '#246131', weekend: '#213a25' } },
  { id: 'sage', name: { en: 'Sage', de: 'Salbei' }, light: { calendar: '#d4e2d6', today: '#95bd9c', weekend: '#c7d3c8' }, dark: { calendar: '#1d281f', today: '#405a45', weekend: '#2b362d' } },
  { id: 'lime', name: { en: 'Lime', de: 'Limette' }, light: { calendar: '#d7e4c4', today: '#9fbf62', weekend: '#c9d4b8' }, dark: { calendar: '#20290f', today: '#475b19', weekend: '#2e371d' } },
  { id: 'olive', name: { en: 'Olive', de: 'Olive' }, light: { calendar: '#dfe0cd', today: '#b3b582', weekend: '#d0d1c0' }, dark: { calendar: '#26261c', today: '#54553b', weekend: '#333429' } },
  { id: 'yellow', name: { en: 'Yellow', de: 'Gelb' }, light: { calendar: '#ece4c5', today: '#d4bc5c', weekend: '#ddd5ba' }, dark: { calendar: '#2a2513', today: '#5e5223', weekend: '#383320' } },
  { id: 'amber', name: { en: 'Amber', de: 'Bernstein' }, light: { calendar: '#edd9bb', today: '#d9a346', weekend: '#dccbb0' }, dark: { calendar: '#2e2312', today: '#684d20', weekend: '#3c311f' } },
  { id: 'orange', name: { en: 'Orange', de: 'Orange' }, light: { calendar: '#f9d6bf', today: '#f49752', weekend: '#e8c8b4' }, dark: { calendar: '#381e0b', today: '#7d4007', weekend: '#462c19' } },
  { id: 'terracotta', name: { en: 'Terracotta', de: 'Terrakotta' }, light: { calendar: '#f3d7cc', today: '#e69c80', weekend: '#e2c9c0' }, dark: { calendar: '#341f18', today: '#744431', weekend: '#422d25' } },
  { id: 'coral', name: { en: 'Coral', de: 'Koralle' }, light: { calendar: '#fcd3cc', today: '#fa8f7e', weekend: '#eac6bf' }, dark: { calendar: '#391c17', today: '#813a30', weekend: '#482924' } },
  { id: 'red', name: { en: 'Red', de: 'Rot' }, light: { calendar: '#fed2cd', today: '#fe8b83', weekend: '#ecc5c1' }, dark: { calendar: '#3a1b19', today: '#833734', weekend: '#492826' } },
  { id: 'rose', name: { en: 'Rose', de: 'Rosa' }, light: { calendar: '#fdd1d6', today: '#fc899d', weekend: '#ebc4c9' }, dark: { calendar: '#3a1a20', today: '#813645', weekend: '#49282d' } },
  { id: 'pink', name: { en: 'Pink', de: 'Pink' }, light: { calendar: '#fad1e0', today: '#f589b6', weekend: '#e9c4d1' }, dark: { calendar: '#381a26', today: '#7e3655', weekend: '#472834' } },
  { id: 'fuchsia', name: { en: 'Fuchsia', de: 'Fuchsia' }, light: { calendar: '#f2d3ee', today: '#e38fdb', weekend: '#e1c5de' }, dark: { calendar: '#331c31', today: '#723b6e', weekend: '#41293f' } },
  { id: 'plum', name: { en: 'Plum', de: 'Pflaume' }, light: { calendar: '#ead6f0', today: '#cf9adf', weekend: '#dac8df' }, dark: { calendar: '#2d1f32', today: '#664370', weekend: '#3b2c40' } },
  { id: 'purple', name: { en: 'Purple', de: 'Violett' }, light: { calendar: '#e3d7fb', today: '#bf9bfc', weekend: '#d3c9e9' }, dark: { calendar: '#291f3a', today: '#5c4383', weekend: '#372d49' } },
  { id: 'lavender', name: { en: 'Lavender', de: 'Lavendel' }, light: { calendar: '#dbdbf8', today: '#aaa7f6', weekend: '#cccde7' }, dark: { calendar: '#232238', today: '#4e4b7f', weekend: '#313047' } },
  { id: 'indigo', name: { en: 'Indigo', de: 'Indigo' }, light: { calendar: '#d2ddff', today: '#96acff', weekend: '#c5ceee' }, dark: { calendar: '#1d233d', today: '#3f4d8c', weekend: '#2a314c' } },
  { id: 'mocha', name: { en: 'Mocha', de: 'Mokka' }, light: { calendar: '#e8dbd1', today: '#cca98e', weekend: '#d9cdc4' }, dark: { calendar: '#2b241e', today: '#604f41', weekend: '#39312b' } },
  { id: 'stone', name: { en: 'Stone', de: 'Stein' }, light: { calendar: '#e2ddd6', today: '#bcaf9c', weekend: '#d3cfc8' }, dark: { calendar: '#272521', today: '#585248', weekend: '#35322e' } },
  { id: 'slate', name: { en: 'Slate', de: 'Schiefer' }, light: { calendar: '#d6dfea', today: '#9db3d0', weekend: '#c9d0da' }, dark: { calendar: '#20262e', today: '#455467', weekend: '#2d333c' } },
  { id: 'graphite', name: { en: 'Graphite', de: 'Graphit' }, light: { calendar: '#dcdee3', today: '#abb1be', weekend: '#cdcfd4' }, dark: { calendar: '#232529', today: '#4e535b', weekend: '#313337' } },
]
