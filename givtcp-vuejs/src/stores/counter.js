import { defineStore } from 'pinia'
import { useSessionStorage } from '@vueuse/core'

// allsettings.json keeps inverters as flat per-slot keys (invertorIP_1, invertorIP_2, ...) plus number_of_inverters.
export function emptyInverter() {
  return { enable: false, ip: '', serial: '', name: '', batteryOnly: false, model: '' }
}

export function isEmptyInverter(inv) {
  return !inv.ip && !inv.serial
}

export function invertersFromSettings(setts) {
  const count = Number(setts.number_of_inverters) || 0
  const list = []
  for (let n = 1; n <= count; n++) {
    list.push({
      enable: setts['inverter_enable_' + n] === true,
      ip: setts['invertorIP_' + n] ?? '',
      serial: setts['serial_number_' + n] ?? '',
      name: setts['inverterName_' + n] ?? '',
      batteryOnly: setts['inverter_battery_only_' + n] === true,
      model: setts['Model_' + n] ?? ''
    })
  }
  // Drop unused slots at the end (the template ships 5), but keep gaps so slot numbers never shift
  while (list.length && isEmptyInverter(list[list.length - 1])) list.pop()
  return list
}

export function invertersToSettings(list) {
  const setts = { number_of_inverters: list.length }
  list.forEach((inv, i) => {
    const n = i + 1
    setts['inverter_enable_' + n] = inv.enable
    setts['invertorIP_' + n] = inv.ip
    setts['serial_number_' + n] = inv.serial
    setts['inverterName_' + n] = inv.name
    setts['inverter_battery_only_' + n] = inv.batteryOnly
    setts['Model_' + n] = inv.model
  })
  return setts
}

export const useTcpStore = defineStore('givtcp-form', {
  state: () => ({
    // One entry per inverter slot; list position + 1 is the slot number GivTCP uses for ports, logs and
    // folders, so entries are never renumbered. Converted to/from the flat allsettings.json keys on load/save.
    inverters: useSessionStorage('inverters', { list: [] }),
    evc: useSessionStorage('evc', {
      evc_enable: false,
      evc_ip_address: "",
      evc_self_run_timer: 10,
      evc_import_max_current: 60
    }),
    selfrun: useSessionStorage('selfrun', {
      auto_scan: true,
      self_run: false,
      self_run_timer: 30,
      self_run_timer_full: 120,
      refresh_max_age: 0,
      HA_Auto_D: true,
    }),
    mqtt: useSessionStorage('mqtt', {
      MQTT_Output: true,
      MQTT_Address: "",
      MQTT_Username: "",
      MQTT_Password: "",
      MQTT_Retain: true,
      //optional
      MQTT_Topic: "GivEnergy",
      MQTT_Port: 1883
    }),
    influx: useSessionStorage('influx', {
      Influx_Output: false,
      influxURL: "",
      influxToken: "",
      influxBucket: "",
      influxOrg: ""
    }),
    tariffs: useSessionStorage('tariffs', {
      dynamic_tariff: false,
      export_rate: 0.04,
      day_rate:0.395,
      day_rate_start: "05:30",
      night_rate: 0.155,
      night_rate_start: "23:30",
    }),
    web: useSessionStorage('web', {
      Web_Dash: true,
      Web_Dash_Port: 3000
    }),
    palm: useSessionStorage('palm', {
      Smart_Target: false,
      GE_API: "",
      SOLCASTAPI:"",
      SOLCASTSITEID:"",
      SOLCASTSITEID2:"",
      PALM_WINTER: "01,02,03,10,11,12",
      PALM_SHOULDER: "04,05,09",
      PALM_MIN_SOC_TARGET: 25,
      PALM_MAX_SOC_TARGET: 45,
      PALM_BATT_RESERVE: 4,
      PALM_BATT_UTILISATION: 0.85,
      PALM_WEIGHT: 35,
      LOAD_HIST_WEIGHT: 1
    }),
    misc: useSessionStorage('misc', {
      TZ: 'Europe/London',
      Print_Raw_Registers: true,
      Log_Level: "Info",
      queue_retries: 2,
      data_smoother: "medium",
      timeslot_entities: "both",
    })
  })
})

export const useStep = defineStore('step', {
  state: () => ({
    step: useSessionStorage('step', -1),
    isNew: useSessionStorage('isNew', true)
  })
})

export const useCard = defineStore('card', {
  state: () => ({
    inverters: {
      title: 'Inverter Config',
      subtitle: 'Add as many inverters as you need. Serial Number and model are filled in automatically when GivTCP finds an inverter.',
      fields: []
    },
    evc: {
      title: 'EVC',
      subtitle: 'Connect to GivEnergy EV Charger and allow control',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'EVC Enable',
            parent: 'evc',
            key: 'evc_enable'
          }
        },
        {
          type: 'text',
          options: {
            label: 'EVC IP',
            parent: 'evc',
            key: 'evc_ip_address'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Timer',
            parent: 'evc',
            key: 'evc_self_run_timer'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Max Import Current',
            parent: 'evc',
            key: 'evc_import_max_current'
          }
        }
      ]
    },
    selfrun: {
      title: 'Self Run',
      subtitle: 'Setup the MQTT broker that stores information about your incoming inverter data',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Auto Scan',
            parent: 'selfrun',
            key: 'auto_scan'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Self Run',
            parent: 'selfrun',
            key: 'self_run'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Self Run Loop Timer',
            parent: 'selfrun',
            key: 'self_run_timer'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Self Run Loop Timer (Full)',
            parent: 'selfrun',
            key: 'self_run_timer_full'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Skip Reads Fresher Than (s, 0=off)',
            parent: 'selfrun',
            key: 'refresh_max_age'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Home Assistant Auto Discovery',
            parent: 'selfrun',
            key: 'HA_Auto_D'
          }
        }
      ]
    },
    mqtt: {
      title: 'MQTT',
      subtitle: 'Setup the MQTT broker that stores information about your incoming inverter data',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Enable',
            parent: 'mqtt',
            key: 'MQTT_Output'
          }
        },
        {
          type: 'text',
          options: {
            label: 'IP Address',
            parent: 'mqtt',
            key: 'MQTT_Address'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Username',
            parent: 'mqtt',
            key: 'MQTT_Username'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Password',
            parent: 'mqtt',
            key: 'MQTT_Password'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Topic',
            parent: 'mqtt',
            key: 'MQTT_Topic'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Port',
            parent: 'mqtt',
            key: 'MQTT_Port'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Retain',
            parent: 'mqtt',
            key: 'MQTT_Retain'
          }
        }
      ]
    },
    influx: {
      title: 'InfluxDB',
      subtitle: 'Setup your InfluxDB instance',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Output',
            parent: 'influx',
            key: 'Influx_Output'
          }
        },
        {
          type: 'text',
          options: {
            label: 'URL',
            parent: 'influx',
            key: 'influxURL'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Token',
            parent: 'influx',
            key: 'influxToken'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Bucket',
            parent: 'influx',
            key: 'influxBucket'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Org',
            parent: 'influx',
            key: 'influxOrg'
          }
        }
      ]
    },
    tariffs: {
      title: 'Tariffs',
      subtitle: 'Setup your Tariffs',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Dynamic',
            parent: 'tariffs',
            key: 'dynamic_tariff'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Export Rate',
            parent: 'tariffs',
            key: 'export_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Day Rate',
            parent: 'tariffs',
            key: 'day_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Day Start',
            parent: 'tariffs',
            key: 'day_rate_start'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Night Rate',
            parent: 'tariffs',
            key: 'night_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Night Start',
            parent: 'tariffs',
            key: 'night_rate_start'
          }
        }
      ]
    },
    web: {
      title: 'Dashboard',
      subtitle: 'Simple in home display dashboard',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Dashboard',
            parent: 'web',
            key: 'Web_Dash'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Port',
            parent: 'web',
            key: 'Web_Dash_Port'
          }
        }
      ]
    },
    palm: {
      title: 'Smart Target',
      subtitle: 'Automtically update your target SOC every night based on olar prediction and historical usage',
      fields: [
        ,{
          type: 'checkbox',
          options: {
            label: 'Enable',
            parent: 'palm',
            key: 'Smart_Target'
          }
        },
        {
          type: 'text',
          options: {
            label: 'GivEnergy API',
            parent: 'palm',
            key: 'GE_API'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast API Key',
            parent: 'palm',
            key: 'SOLCASTAPI'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast Site ID 1',
            parent: 'palm',
            key: 'SOLCASTSITEID'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast Site ID 2',
            parent: 'palm',
            key: 'SOLCASTSITEID2'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Winter',
            parent: 'palm',
            key: 'PALM_WINTER'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Shoulder',
            parent: 'palm',
            key: 'PALM_SHOULDER'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Minimum SoC Target',
            parent: 'palm',
            key: 'PALM_MIN_SOC_TARGET'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Maximum SoC Target',
            parent: 'palm',
            key: 'PALM_MAX_SOC_TARGET'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Battery Reserve',
            parent: 'palm',
            key: 'PALM_BATT_RESERVE'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Battery Utilisation',
            parent: 'palm',
            key: 'PALM_BATT_UTILISATION'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Weight',
            parent: 'palm',
            key: 'PALM_WEIGHT'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Historical Weight',
            parent: 'palm',
            key: 'LOAD_HIST_WEIGHT'
          }
        }
      ]
    },
    misc: {
      title: 'Misc',
      subtitle: 'Setup Any Miscellaneous variables',
      fields: [
        {
          type: 'text',
          options: {
            label: 'Timezone',
            parent: 'misc',
            key: 'TZ'
          }
        },
        {
          type: 'select',
          options: {
            label: 'Log Level',
            parent: 'misc',
            items: ["critical", "info", "debug","write_debug"],
            key: 'Log_Level'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Print Raw',
            parent: 'misc',
            key: 'Print_Raw_Registers'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Queue Retries',
            parent: 'misc',
            key: 'queue_retries'
          }
        },
        {
          type: 'select',
          options: {
            label: 'Smoothing',
            parent: 'misc',
            items: ["high", "medium", "low","none"],
            key: 'data_smoother'
          }
        },
        {
          type: 'select',
          options: {
            label: 'Timeslot entities in Home Assistant',
            parent: 'misc',
            items: [
              { title: 'Drop-down and time picker', value: 'both' },
              { title: 'Time picker only', value: 'time' },
              { title: 'Drop-down only', value: 'dropdown' }
            ],
            key: 'timeslot_entities'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Timezone',
            parent: 'misc',
            key: 'TZ'
          }
        },
      ]
    }
  })
})
