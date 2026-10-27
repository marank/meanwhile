import { ref } from 'vue'

/**
 * Whether a page shown on its own (route meta `standalone`) belongs in the app's frame after all: the
 * invitation page, opened by the participant themselves while signed in.
 */
export const standaloneFramed = ref(false)
