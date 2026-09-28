<template>
  <div class="flex-gap">
    <v-btn v-if="storeStep.step > -1" @click="storeStep.step = storeStep.step - 1">
      Previous
    </v-btn>
    <v-btn v-if="storeStep.step > -1" @click="restartgivtcp()"> 
      Save and Restart
    </v-btn>
    
    <v-btn v-if="storeStep.step < 8" @click="storeStep.step = storeStep.step + 1"> 
      Next
    </v-btn>
    <v-snackbar
      v-model="snackbar"
      :color="message === 'Success' ? '#4fbba9' : 'red'"
      timeout="2000"
    >
      {{ message }}

      <template v-slot:actions>
        <v-btn
          color="white"
          variant="text"
          @click="snackbar = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script>
import { useTcpStore, useStep, invertersFromSettings, invertersToSettings } from '@/stores/counter'
import Setup from './Setup.vue'

const settingfile = "allsettings.json"
export default {
  name: 'Setup',
  data() {
    return {
      storeStep: useStep(),
      storeTCP: useTcpStore(),
      snackbar:false,
      message:""
    }
  },
  methods: {
    // Flat settings object for allsettings.json; inverters are stored as a list and flattened here
    collectSettings() {
      return {
        ...this.storeTCP.web,
        ...this.storeTCP.mqtt,
        ...invertersToSettings(this.storeTCP.inverters.list || []),
        ...this.storeTCP.influx,
        ...this.storeTCP.selfrun,
        ...this.storeTCP.tariffs,
        ...this.storeTCP.misc,
        ...this.storeTCP.palm,
        ...this.storeTCP.evc
      }
    },
    applySettings(getJSON) {
      this.storeTCP.inverters.list = invertersFromSettings(getJSON)
      for (const section of ['web', 'mqtt', 'influx', 'selfrun', 'tariffs', 'misc', 'palm', 'evc']) {
        for (const key of Object.keys(this.storeTCP[section])) {
          if (key in getJSON) this.storeTCP[section][key] = getJSON[key]
        }
      }
    },
    async restartgivtcp() {
      try{
        const data = this.collectSettings()
      // Write to json file here
        const settingdata = JSON.stringify(data);

        // Relative URLs resolve against the page, so this works direct (8099/8098) and via HA ingress
        const setResponse = await fetch('settings',{
        method:"POST",
        headers:{
          "Content-Type":"application/json"
        },
         body:JSON.stringify(data)
        })

        if(!setResponse.ok){
          this.snackbar = true
          this.message = `Error Saving config change`
        }

        const res = await fetch('REST1/restart')
        console.log(res)
        if(res.ok){
          this.snackbar = true
          this.message = "Restarting GivTCP..."
        }
      } catch(e){
        this.snackbar = false
        this.message = "GivTCP not restarted... try manually"
      }
    }
  },
  async created() {
    await fetch('settings').then(response => {
          return response.json();
        }).then(getJSON => {
          this.applySettings(getJSON)
        }).catch(err => {
            this.snackbar = true
            this.message = `Error: ${err}`
        });

    },
    watch: {
    storeStep:{
      async handler() {
        try{
          this.snackbar = false
          this.message = ""

          const data = this.collectSettings()
      // Write to json file here
        const settingdata = JSON.stringify(data);

        const host = 'settings'
        const setResponse = await fetch(host,{
        method:"POST",
        headers:{
          "Content-Type":"application/json"
        },
         body:JSON.stringify(data)
        })

        if(!setResponse.ok){
          this.snackbar = true
          this.message = `Error Saving config change`
        }
        else {
          this.snackbar = false
          this.message = `Success: Saving config change`
        }

        await fetch(host).then(response => {
          return response.json();
        }).then(getJSON => {
          
        this.applySettings(getJSON);
        }).catch(err => {
            this.snackbar = true
            this.message = `Error: ${err}`
        });

        }catch(e){
          this.snackbar = true
          this.message = `Error: ${e}`
        }
    },
    deep:true
    }
  }
}
</script>

<style scoped>
.flex-gap{
  display: inline-flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>