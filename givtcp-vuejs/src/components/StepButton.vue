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
import { useTcpStore, useStep } from '@/stores/counter'
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
    async restartgivtcp() {
      try{
        const data = {
          ...this.storeTCP.web,
          ...this.storeTCP.mqtt,
          ...this.storeTCP.inverters,
          ...this.storeTCP.influx,
          ...this.storeTCP.selfrun,
          ...this.storeTCP.tariffs,
          ...this.storeTCP.misc,
          ...this.storeTCP.palm,
          ...this.storeTCP.evc
        }
      // Write to json file here
        const settingdata = JSON.stringify(data);

        await fetch('hostip.json').then(response => {
          return response.json();
          }).then(json => {
              this.n=json;
          })
        if (window.location.protocol == "https:"){
              var host = "https://" + n +":8098/settings"
            }
            else{
              var host = "http://" + n +":8099/settings"
            }
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

        if (window.location.protocol == "https:"){
          var host = "https://" + n +":8098/REST1/restart"
        }
        else{
          var host = "http://" + n +":8099/REST1/restart"
        }
        const res = await fetch(host)
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
    await fetch('hostip.json').then(response => {
          return response.json();
      }).then(json => {
          this.n=json;
      })
    if (window.location.protocol == "https:"){
          var host = "https://" + n +":8098/settings"
        }
        else{
          var host = "http://" + n +":8099/settings"
        }
    await fetch(host).then(response => {
          return response.json();
        }).then(getJSON => {
          const data = {
          ...this.storeTCP.web,
          ...this.storeTCP.mqtt,
          ...this.storeTCP.inverters,
          ...this.storeTCP.influx,
          ...this.storeTCP.selfrun,
          ...this.storeTCP.tariffs,
          ...this.storeTCP.misc,
          ...this.storeTCP.palm,
          ...this.storeTCP.evc
        }
          Object.keys(data).map((key)=>{
          if(key in this.storeTCP.web){
            this.storeTCP.web[key] = getJSON[key]
          }else if(key in this.storeTCP.mqtt){
            this.storeTCP.mqtt[key] = getJSON[key]
          }else if(key in this.storeTCP.inverters){
            this.storeTCP.inverters[key] = getJSON[key]
          }else if(key in this.storeTCP.influx){
            this.storeTCP.influx[key] = getJSON[key]
          }else if(key in this.storeTCP.selfrun){
            this.storeTCP.selfrun[key] = getJSON[key]
          }else if(key in this.storeTCP.tariffs){
            this.storeTCP.tariffs[key] = getJSON[key]
          }else if(key in this.storeTCP.misc){
            this.storeTCP.misc[key] = getJSON[key]
          }else if(key in this.storeTCP.palm){
            this.storeTCP.palm[key] = getJSON[key]
          }else if(key in this.storeTCP.evc){
            this.storeTCP.evc[key] = getJSON[key]
          }else {
            return
          }
          })
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

          const data = {
          ...this.storeTCP.web,
          ...this.storeTCP.mqtt,
          ...this.storeTCP.inverters,
          ...this.storeTCP.influx,
          ...this.storeTCP.selfrun,
          ...this.storeTCP.tariffs,
          ...this.storeTCP.misc,
          ...this.storeTCP.palm,
          ...this.storeTCP.evc
        }
      // Write to json file here
        const settingdata = JSON.stringify(data);

        await fetch('hostip.json').then(response => {
          return response.json();
          }).then(json => {
              this.n=json;
          })
        if (window.location.protocol == "https:"){
              var host = "https://" + n +":8098/settings"
            }
            else{
              var host = "http://" + n +":8099/settings"
            }
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
          
        Object.keys(data).map((key)=>{
          if(key in this.storeTCP.web){
            this.storeTCP.web[key] = getJSON[key]
          }else if(key in this.storeTCP.mqtt){
            this.storeTCP.mqtt[key] = getJSON[key]
          }else if(key in this.storeTCP.inverters){
            this.storeTCP.inverters[key] = getJSON[key]
          }else if(key in this.storeTCP.influx){
            this.storeTCP.influx[key] = getJSON[key]
          }else if(key in this.storeTCP.selfrun){
            this.storeTCP.selfrun[key] = getJSON[key]
          }else if(key in this.storeTCP.tariffs){
            this.storeTCP.tariffs[key] = getJSON[key]
          }else if(key in this.storeTCP.misc){
            this.storeTCP.misc[key] = getJSON[key]
          }else if(key in this.storeTCP.palm){
            this.storeTCP.palm[key] = getJSON[key]
          }else if(key in this.storeTCP.evc){
            this.storeTCP.evc[key] = getJSON[key]
          }else {
            return
          }
        });
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