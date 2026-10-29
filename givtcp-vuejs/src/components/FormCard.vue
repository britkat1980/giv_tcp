<template>
  <div>
    <v-card>
      <v-card-title> {{ card?.title }} </v-card-title>
      <v-card-subtitle> {{ card?.subtitle }} </v-card-subtitle>
      <v-card-text>
        <div v-for="(input, i) in card?.fields" :key="i">
          <v-select
            v-if="input?.type === 'select'"
            :label="input?.options?.label"
            :items="input?.options?.items"
            v-model="storeTCP[input?.options?.parent][input?.options?.key]"
          />
          <v-text-field
            v-else-if="input?.type === 'text'"
            v-model="storeTCP[input?.options?.parent][input?.options?.key]"
            :label="input?.options?.label"
            :type="input?.options?.password ? 'password' : 'text'"
            :autocomplete="input?.options?.password ? 'new-password' : undefined"
          />
          <v-switch
            v-else-if="input?.type === 'checkbox'"
            v-model="storeTCP[input?.options?.parent][input?.options?.key]"
            :label="input?.options?.label"
            color='#4fbba9'
          />
          <div v-else-if="input?.type === 'button'">
            <v-btn
            v-model="storeTCP[input?.options?.parent][input?.options?.key]"
            @click='input?.options?.onClick'
            color='#4fbba9'
            style="color:white;"
          >{{input?.options?.label}}</v-btn>
          <h3>{{ storeTCP.restart.hasRestarted != null ? storeTCP.restart.hasRestarted ? "GivTCP Restarted Successfully" : "GivTCP Failed to Restart. Try Restarting Manually" : ''}}</h3>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { useTcpStore } from '@/stores/counter'

export default {
  name: 'FormCard',

  props: {
    card: {
      required: true,
      type: Object
    }
  },

  data() {
    return {
      storeTCP: useTcpStore()
    }
  },
  watch:{
    storeTCP:{
      async handler(){
        setTimeout(() => this.storeTCP.restart.hasRestarted = null,10000)
      },
      deep:true
    }
  }
}
</script>

<style scoped></style>
