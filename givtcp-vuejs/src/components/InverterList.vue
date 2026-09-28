<template>
  <div>
    <v-card>
      <v-card-title class="d-flex align-center">
        {{ card?.title }}
        <v-spacer />
        <v-btn color="#4fbba9" style="color: white" @click="addInverter()">
          Add inverter
        </v-btn>
      </v-card-title>
      <v-card-subtitle> {{ card?.subtitle }} </v-card-subtitle>
      <v-card-text>
        <p v-if="!list.length" class="ma-4">
          No inverters configured yet. Add one, or pick one found on the network below.
        </p>

        <v-expansion-panels multiple>
          <v-expansion-panel v-for="(inv, i) in list" :key="i">
            <v-expansion-panel-title>
              <div class="d-flex flex-wrap align-center" style="gap: 12px; width: 100%">
                <strong>{{ i + 1 }}.</strong>
                <template v-if="isEmpty(inv)">
                  <span class="text-medium-emphasis">Empty slot</span>
                </template>
                <template v-else>
                  <span>{{ inv.name || defaultName(i) }}</span>
                  <span class="text-medium-emphasis">{{ inv.serial || 'serial not known yet' }}</span>
                  <span class="text-medium-emphasis">{{ inv.ip }}</span>
                  <span v-if="inv.model" class="text-medium-emphasis">{{ inv.model }}</span>
                  <v-chip size="small" :color="inv.enable ? '#4fbba9' : 'grey'">
                    {{ inv.enable ? 'Enabled' : 'Disabled' }}
                  </v-chip>
                </template>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-switch v-model="inv.enable" label="Enable" color="#4fbba9" />
              <v-text-field v-model="inv.ip" label="IP Address" />
              <v-text-field v-model="inv.serial" label="Serial Number" />
              <v-text-field v-model="inv.name" :label="'Friendly Name (HA Device Prefix), eg. ' + defaultName(i)" />
              <v-switch
                v-model="inv.batteryOnly"
                label="Only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)"
                color="#4fbba9"
              />
              <p class="text-caption mb-2">
                Slot {{ i + 1 }}: REST API on port {{ restPort(i + 1) }} (/REST{{ i + 1 }}/). Slot numbers stay
                fixed so existing Home Assistant and Predbat setups keep working.
              </p>
              <v-btn variant="outlined" color="red" @click="removeInverter(i)">
                Remove inverter
              </v-btn>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <div v-if="notConfigured.length" class="mt-6">
          <h3 class="mb-2">Found on the last network scan but not configured</h3>
          <v-list density="compact">
            <v-list-item v-for="found in notConfigured" :key="found.Serial_Number">
              <v-list-item-title>
                {{ found.Serial_Number }} at {{ found.IP_Address }}
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ found.Model }}, {{ found.Number_of_Batteries }} batteries
              </v-list-item-subtitle>
              <template v-slot:append>
                <v-btn color="#4fbba9" style="color: white" size="small" @click="addFound(found)">Add</v-btn>
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { useTcpStore, emptyInverter, isEmptyInverter } from '@/stores/counter'

export default {
  name: 'InverterList',

  props: {
    card: {
      required: true,
      type: Object
    }
  },

  data() {
    return {
      storeTCP: useTcpStore(),
      found: []
    }
  },

  computed: {
    list() {
      // Older sessions stored the 5 flat inverter fields here; start clean if so
      if (!Array.isArray(this.storeTCP.inverters.list)) this.storeTCP.inverters.list = []
      return this.storeTCP.inverters.list
    },
    notConfigured() {
      const known = this.list.map((inv) => inv.serial).filter((sn) => sn)
      return this.found.filter((f) => !known.includes(f.Serial_Number))
    }
  },

  methods: {
    isEmpty: isEmptyInverter,
    defaultName(i) {
      // Matches the default startup.py gives new slots
      return i === 0 ? 'GivTCP' : 'GivTCP' + (i + 1)
    },
    restPort(slot) {
      // Same rule as startup.py invPort(): 6345-6349 for slots 1-5, then 6356 onwards (6350 is the settings API)
      return slot <= 5 ? 6344 + slot : 6350 + slot
    },
    addInverter(details = {}) {
      // Reuse the first empty slot so numbering stays compact, otherwise add a new slot at the end
      let i = this.list.findIndex(isEmptyInverter)
      if (i === -1) {
        this.list.push(emptyInverter())
        i = this.list.length - 1
      }
      this.list[i] = { ...emptyInverter(), enable: true, name: this.defaultName(i), ...details }
    },
    addFound(found) {
      this.addInverter({ ip: found.IP_Address, serial: found.Serial_Number, model: found.Model })
    },
    removeInverter(i) {
      if (i === this.list.length - 1) {
        // Last slot: drop it, and any empty slots it leaves at the end
        this.list.pop()
        while (this.list.length && isEmptyInverter(this.list[this.list.length - 1])) this.list.pop()
      } else {
        // Clear it but keep the slot, so the inverters after it keep their numbers (ports, logs, HA entities)
        this.list[i] = emptyInverter()
      }
    },
    async loadFound() {
      try {
        const res = await fetch('settings/found')
        if (res.ok) this.found = await res.json()
      } catch (e) {
        this.found = []     // no scan results available; the list simply isn't shown
      }
    }
  },

  created() {
    this.loadFound()
  }
}
</script>

<style scoped></style>
