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
        <div v-if="card?.title === 'MQTT'" class="mqtt-test-section">
          <v-btn
            :loading="storeTCP.mqtt_test.in_progress"
            color="#4fbba9"
            style="color:white;"
            @click="testMqttConnection"
          >
            TEST MQTT CONNECTION
          </v-btn>
          <p
            v-if="storeTCP.mqtt_test.message"
            :class="storeTCP.mqtt_test.success ? 'mqtt-test-message-success' : 'mqtt-test-message-error'"
          >
            {{ storeTCP.mqtt_test.message }}
          </p>
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
  methods: {
    clearMqttTestStatus() {
      if (this.storeTCP.mqtt_test.in_progress) {
        return
      }
      this.storeTCP.mqtt_test.success = null
      this.storeTCP.mqtt_test.message = ""
    },
    setMqttTestStatus(success, message) {
      this.storeTCP.mqtt_test.success = success
      this.storeTCP.mqtt_test.message = `${success ? 'Success' : 'Failure'}: ${message}`
    },
    shouldUseCurrentOrigin() {
      return (
        window.location.port === "8099" ||
        window.location.port === "8098" ||
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
      )
    },
    async getMqttTestHost() {
      let host = window.location.hostname
      try {
        const response = await fetch('hostip.json')
        if (response.ok) {
          const hostIp = await response.json()
          if (hostIp) {
            host = hostIp
          }
        }
      } catch (e) {
        host = window.location.hostname
      }

      if (this.shouldUseCurrentOrigin()) {
        return `${window.location.origin}/settings/mqtt/test`
      }
      if (window.location.protocol == "https:") {
        return "https://" + host + ":8098/settings/mqtt/test"
      }
      return "http://" + host + ":8099/settings/mqtt/test"
    },
    async testMqttConnection() {
      const address = String(this.storeTCP.mqtt.MQTT_Address || "").trim()
      const port = Number(this.storeTCP.mqtt.MQTT_Port)

      if (address === "") {
        this.setMqttTestStatus(false, "MQTT host is required")
        return
      }
      if (Number.isNaN(port) || port < 1 || port > 65535) {
        this.setMqttTestStatus(false, "MQTT port must be a number between 1 and 65535")
        return
      }

      this.storeTCP.mqtt_test.in_progress = true
      this.storeTCP.mqtt_test.success = null
      this.storeTCP.mqtt_test.message = ""

      try {
        const response = await fetch(await this.getMqttTestHost(), {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            MQTT_Address: address,
            MQTT_Port: port,
            MQTT_Username: this.storeTCP.mqtt.MQTT_Username,
            MQTT_Password: this.storeTCP.mqtt.MQTT_Password
          })
        })
        const result = await response.json()
        this.setMqttTestStatus(Boolean(result?.ok), result?.message || "MQTT test failed")
      } catch (e) {
        this.setMqttTestStatus(false, "Unable to reach the MQTT test service")
      } finally {
        this.storeTCP.mqtt_test.in_progress = false
      }
    }
  },
  watch:{
    'storeTCP.mqtt': {
      handler() {
        this.clearMqttTestStatus()
      },
      deep: true
    },
    storeTCP:{
      async handler(){
        setTimeout(() => this.storeTCP.restart.hasRestarted = null,10000)
      },
      deep:true
    }
  }
}
</script>

<style scoped>
.mqtt-test-section {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.mqtt-test-message-success,
.mqtt-test-message-error {
  margin: 0;
  font-size: 1rem;
  line-height: 1.4;
}
.mqtt-test-message-success {
  color: #2e7d32;
}
.mqtt-test-message-error {
  color: #b00020;
}
</style>
