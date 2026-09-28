<template>
  <div>
    <v-timeline direction="horizontal" align="start" side="end">
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
    <v-container>
      <h1 class="text-center" v-if="storeStep.step === -1">
        Welcome to the GivTCP setup page
      </h1>
      <h2 class="text-center" v-if="storeStep.step === -1">
        This config page is where you are able to tweak the configuration of GivTCP to suit your needs. <br>
        GivTCP will add in any inverters it finds into the inverters page, but you are able to tweak them as needed.<br>
        The first time you run this you will need to check the details then turn on "Self Run" to start GivTCP.<br>
        You need to restart GivTCP after making any changes to the configuration.<br>
      </h2>
      <div class="d-flex flex-1-1-100 justify-center ma-5">
        <StepButton />
      </div>
      <InverterList
        v-if="storeStep.step >= 0 && timelineList[storeStep.step] === 'inverters'"
        :card="storeCard.inverters"
      />
      <FormCard v-else-if="storeStep.step >= 0" :card="storeCard[timelineList[storeStep.step]]" />
    </v-container>
  </div>
</template>

<script>
import FormCard from '@/components/FormCard.vue'
import InverterList from '@/components/InverterList.vue'
import StepButton from '@/components/StepButton.vue'
import { useTcpStore, useStep, useCard } from '@/stores/counter'

export default {
  name: 'Setup',
  components: {
    FormCard,
    InverterList,
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

<style scoped></style>
