<template>
  <div>
    <!--
      Section navigation and the step actions stay put while the form scrolls,
      so switching section or saving never requires scrolling back up.
    -->
    <div class="gtcp-sticky-nav">
    <v-timeline
      v-if="!$vuetify.display.smAndDown"
      direction="horizontal"
      align="start"
      side="end"
    >
      <v-timeline-item
        v-for="(timeline, i) in timelineList"
        :key="i"
        :dot-color="i <= storeStep.step ? '#4fbba9' : '#000'"
        size="small"
        @click="storeStep.step = i"
      >
        <div
          :style="{
            textTransform: timeline === 'mqtt' ? 'uppercase' : 'capitalize'
          }, {
            textTransform: timeline === 'evc' ? 'uppercase' : 'capitalize'
          }"
        >
          {{ timeline === 'homeAssistant' ? 'Home Assistant' : timeline }}
        </div>
      </v-timeline-item>
    </v-timeline>
    <!--
      Narrow screens: the horizontal timeline neither wraps nor scrolls, so it
      needs as much width as all the section labels combined. In portrait that
      is not available and the labels become unreadable. Wrapping chips use the
      width that is available and keep every section visible and one tap away.
    -->
    <v-chip-group v-else column class="px-3 pt-3">
      <!-- Step -1 is the welcome page, which has no entry in timelineList. -->
      <v-chip
        size="small"
        :color="storeStep.step === -1 ? '#4fbba9' : undefined"
        :variant="storeStep.step === -1 ? 'flat' : 'outlined'"
        @click="storeStep.step = -1"
      >
        Welcome
      </v-chip>
      <v-chip
        v-for="(timeline, i) in timelineList"
        :key="i"
        size="small"
        :color="i === storeStep.step ? '#4fbba9' : undefined"
        :variant="i === storeStep.step ? 'flat' : 'outlined'"
        :style="{ textTransform: timeline === 'evc' ? 'uppercase' : 'capitalize' }"
        @click="storeStep.step = i"
      >
        {{ timeline === 'homeAssistant' ? 'Home Assistant' : timeline }}
      </v-chip>
    </v-chip-group>
      <div class="d-flex flex-1-1-100 justify-center py-2">
        <StepButton />
      </div>
    </div>
    <v-container>
      <h1 class="text-center" v-if="storeStep.step === -1">
        Welcome to the GivTCP setup page
      </h1>
      <!--
        Body copy, so paragraphs rather than a heading full of <br> tags: as an
        h2 this rendered at heading size, which is overwhelming on a phone.
        base.css zeroes margins on everything, hence the explicit mb-4.
      -->
      <div class="text-center" v-if="storeStep.step === -1">
        <p class="mb-4">
          This config page is where you are able to tweak the configuration of GivTCP to suit your needs.
        </p>
        <p class="mb-4">
          GivTCP will add in any inverters it finds into the inverters page, but you are able to tweak them as needed.
        </p>
        <p class="mb-4">
          The first time you run this you will need to check the details then turn on "Self Run" to start GivTCP.
        </p>
        <p>
          You need to restart GivTCP after making any changes to the configuration.
        </p>
      </div>
      <FormCard v-if="storeStep.step >= 0" :card="storeCard[timelineList[storeStep.step]]" />
    </v-container>
  </div>
</template>

<script>
import FormCard from '@/components/FormCard.vue'
import StepButton from '@/components/StepButton.vue'
import { useTcpStore, useStep, useCard } from '@/stores/counter'

export default {
  name: 'Setup',
  components: {
    FormCard,
    StepButton
  },
  data() {
    return {
      storeStep: useStep(),
      storeTCP: useTcpStore(),
      storeCard: useCard()
    }
  },
  computed: {
    timelineList() {
      return Object.keys(this.storeTCP).filter(
        (v) => !v.includes('$') && !v.includes('_') && v !== 'set' && v !== 'get'
      )
    }
  }
}
</script>

<style scoped>
.gtcp-sticky-nav {
  position: sticky;
  top: 0;
  z-index: 5;
  /*
    Match the page itself rather than Vuetify's theme variables: with no v-app
    wrapper the Vuetify theme is fixed to light, so --v-theme-background stays
    white even in dark mode. These are the pair body uses in base.css, and they
    flip together under prefers-color-scheme, keeping the chips legible in both.
  */
  background: var(--color-background);
  color: var(--color-text);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}
</style>
