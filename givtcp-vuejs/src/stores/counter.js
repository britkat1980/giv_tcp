import { defineStore } from 'pinia'
import { useSessionStorage } from '@vueuse/core'

export const useTcpStore = defineStore('givtcp-form', {
  state: () => ({
    inverters: useSessionStorage('inverters', {
      inverter_enable_1: true,
      invertorIP_1: "",
      serial_number_1: "",
      inverterName_1: "",
      inverter_battery_only_1: false,
      inverter_enable_2: false,
      invertorIP_2: "",
      serial_number_2: "",
      inverterName_2: "",
      inverter_battery_only_2: false,
      inverter_enable_3: false,
      invertorIP_3: "",
      serial_number_3: "",
      inverterName_3: "",
      inverter_battery_only_3: false,
      inverter_enable_4: false,
      invertorIP_4: "",
      serial_number_4: "",
      inverterName_4: "",
      inverter_battery_only_4: false,
      inverter_enable_5: false,
      invertorIP_5: "",
      serial_number_5: "",
      inverterName_5: "",
      inverter_battery_only_5: false,
    }),
    evc: useSessionStorage('evc', {
      evc_enable: false,
      evc_ip_address: "",
      evc_self_run_timer: 10,
      evc_import_max_current: 60
    }),
    selfrun: useSessionStorage('selfrun', {
      self_run: false,
      self_run_timer: 30,
      self_run_timer_full: 120,
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
      subtitle: 'Key Invertor details. Serial Number will be automatically added.',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 1 Enable',
            parent: 'inverters',
            key: 'inverter_enable_1'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 1 IP Address',
            parent: 'inverters',
            key: 'invertorIP_1'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 1 Serial Number',
            parent: 'inverters',
            key: 'serial_number_1'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 1 Friendly Name (HA Device Prefix)',
            parent: 'inverters',
            key: 'inverterName_1'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 1 only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)',
            parent: 'inverters',
            key: 'inverter_battery_only_1'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 2 Enable',
            parent: 'inverters',
            key: 'inverter_enable_2'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 2 IP Address',
            parent: 'inverters',
            key: 'invertorIP_2'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 2 Serial Number',
            parent: 'inverters',
            key: 'serial_number_2'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 2 Friendly Name (HA Device Prefix)',
            parent: 'inverters',
            key: 'inverterName_2'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 2 only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)',
            parent: 'inverters',
            key: 'inverter_battery_only_2'
          }
        },

        {
          type: 'checkbox',
          options: {
            label: 'Inverter 3 Enable',
            parent: 'inverters',
            key: 'inverter_enable_3'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 3 IP Address',
            parent: 'inverters',
            key: 'invertorIP_3'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 3 Serial Number',
            parent: 'inverters',
            key: 'serial_number_3'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 3 Friendly Name (HA Device Prefix)',
            parent: 'inverters',
            key: 'inverterName_3'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 3 only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)',
            parent: 'inverters',
            key: 'inverter_battery_only_3'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 4 Enable',
            parent: 'inverters',
            key: 'inverter_enable_4'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 4 IP Address',
            parent: 'inverters',
            key: 'invertorIP_4'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 4 Serial Number',
            parent: 'inverters',
            key: 'serial_number_4'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 4 Friendly Name (HA Device Prefix)',
            parent: 'inverters',
            key: 'inverterName_4'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 4 only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)',
            parent: 'inverters',
            key: 'inverter_battery_only_4'
          }
        },

        {
          type: 'checkbox',
          options: {
            label: 'Inverter 5 Enable',
            parent: 'inverters',
            key: 'inverter_enable_5'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 5 IP Address',
            parent: 'inverters',
            key: 'invertorIP_5'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 5 Serial Number',
            parent: 'inverters',
            key: 'serial_number_5'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Inverter 5 Friendly Name (HA Device Prefix)',
            parent: 'inverters',
            key: 'inverterName_5'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Inverter 5 only report battery data (for use when this inverter is connected to EMS or Gateway in parallel mode)',
            parent: 'inverters',
            key: 'inverter_battery_only_5'
          }
        },

      ]
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
