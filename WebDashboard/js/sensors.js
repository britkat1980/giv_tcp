import { CombinatorType, Prefix, SensorType, Suffix } from './enums.js';
import { Converters } from './converters.js';
import { Formatters } from './formatters.js';

const GatewaySensors = [{
    id: 'Gateway_Details',
    type: SensorType.Summary
}];

const InverterSensors = [{
    id: 'Last_Updated_Time',
    mapping: [
        'Last_Updated_Time',
        'Stats.Last_Updated_Time'
    ],
    combinator: {
        singlePhaseSingleInverter: CombinatorType.EarliestDate,
        singlePhaseMultipleInverters: CombinatorType.EarliestDate,
        multiplePhases: CombinatorType.EarliestDate
    }
}, {
    id: 'Charge_Power',
    mapping: [
        'Power.Power.Charge_Power',
        'Power.Power.Battery_Charge_Power'
    ],
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Discharge_Power',
    mapping: [
        'Power.Power.Discharge_Power',
        'Power.Power.Battery_Discharge_Power'
    ],
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Load_Power',
    mapping: 'Power.Power.Load_Power',
    type: SensorType.Power,
    textElementId: 'power_home_text',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Ignore,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Export_Power',
    mapping: 'Power.Power.Export_Power',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Grid_Power',
    mapping: [
        'Power.Power.Grid_Power',
        'Power.Power.Grid_Apparent_Power'
    ],
    type: SensorType.Power,
    nonZeroValueCheck: [
        'Solar_to_Grid',
        'Grid_to_Battery',
        'Grid_to_House',
        'Battery_to_Grid'
    ],
    textElementId: 'power_grid_text',
    converter: Converters.wattsToKw,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'PV_Power',
    mapping: 'Power.Power.PV_Power',
    type: SensorType.Power,
    textElementId: 'power_solar_text',
    converter: Converters.wattsToKw,
    suffix: Suffix.Power,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Battery_Power',
    mapping: 'Power.Power.Battery_Power',
    type: SensorType.Power,
    textElementId: 'power_battery_text',
    converter: Converters.wattsToKw,
    suffix: Suffix.Power,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Grid_to_Battery',
    mapping: 'Power.Flows.Grid_to_Battery',
    type: SensorType.Flow,
    nonZeroValueCheck: [
        'Grid_Power'
    ],
    flowElementId: 'battery_with_grid',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Grid_to_House',
    mapping: 'Power.Flows.Grid_to_House',
    type: SensorType.Flow,
    nonZeroValueCheck: [
        'Grid_Power'
    ],
    flowElementId: 'grid_to_home',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Solar_to_Battery',
    mapping: 'Power.Flows.Solar_to_Battery',
    type: SensorType.Flow,
    nonZeroValueCheck: [
        'Battery_Power'
    ],
    flowElementId: 'solar_to_battery',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Solar_to_Grid',
    mapping: 'Power.Flows.Solar_to_Grid',
    type: SensorType.Flow,
    nonZeroValueCheck: [
        'Grid_Power'
    ],
    flowElementId: 'solar_to_grid',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Solar_to_House',
    mapping: 'Power.Flows.Solar_to_House',
    type: SensorType.Flow,
    flowElementId: 'solar_to_home',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Battery_to_Grid',
    mapping: 'Power.Flows.Battery_to_Grid',
    type: SensorType.Flow,
    nonZeroValueCheck: [
        'Grid_Power'
    ],
    flowElementId: 'battery_with_grid',
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Battery_to_House',
    mapping: 'Power.Flows.Battery_to_House',
    type: SensorType.Flow,
    flowElementId: 'battery_to_home',
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Load_Energy_Today_kWh',
    mapping: 'Energy.Today.Load_Energy_Today_kWh',
    textElementId: 'energy_home_text',
    type: SensorType.Summary,
    suffix: Suffix.Energy,
    formatter: Formatters.roundToOneDecimalPlace,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Average,   // All inverters might know about the total load?
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'PV_Energy_Today_kWh',
    mapping: 'Energy.Today.PV_Energy_Today_kWh',
    textElementId: 'energy_solar_text',
    type: SensorType.Summary,
    suffix: Suffix.Energy,
    formatter: Formatters.roundToOneDecimalPlace,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'daily_energy_peak',
    mapping: 'Energy.Rates.Day_Energy_kWh',
    textElementId: 'energy_imported_peak_text',
    type: SensorType.Summary,
    formatter: Formatters.roundToOneDecimalPlace,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,   // Temporarily use total peak/off-peak kWh from first inverter - second inverter usage jumps up randomly (issue in GivTCP?)
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'daily_energy_offpeak',
    mapping: 'Energy.Rates.Night_Energy_kWh',
    textElementId: 'energy_imported_offpeak_text',
    type: SensorType.Summary,
    formatter: Formatters.roundToOneDecimalPlace,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,   // Temporarily use total peak/off-peak kWh from first inverter - second inverter usage jumps up randomly (issue in GivTCP?)
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Export_Energy_Today_kWh',
    mapping: 'Energy.Today.Export_Energy_Today_kWh',
    textElementId: 'energy_exported_text',
    type: SensorType.Summary,
    formatter: Formatters.roundToOneDecimalPlace,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Average,   // Each inverter appears to know the same total export amount, but they're off by a very small amount, so use an average.
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Battery_State',
    textElementId: 'battery_state_text',
    type: SensorType.Summary,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Ignore,
        multiplePhases: CombinatorType.Ignore
    }
}, {
    id: 'Battery_State_of_Charge',
    mapping: 'Power.Power.SOC',
    textElementId: 'battery_percentage_text',
    type: SensorType.Summary,
    formatter: Formatters.roundToWholeNumber,
    suffix: Suffix.Percent,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Average,
        multiplePhases: CombinatorType.Average
    }
}, {
    id: 'Battery_Target_State_of_Charge',
    mapping: 'Control.Target_SOC',
    formatter: Formatters.roundToWholeNumber,
    suffix: Suffix.Percent,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Average,
        multiplePhases: CombinatorType.Average
    }
}, {
    id: 'daily_energy_cost_peak',
    mapping: 'Energy.Rates.Day_Cost',
    textElementId: 'energy_imported_peak_cost_text',
    type: SensorType.Summary,
    prefix: Prefix.Currency,
    converter: Converters.numberToCurrency,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'daily_energy_cost_offpeak',
    mapping: 'Energy.Rates.Night_Cost',
    textElementId: 'energy_imported_offpeak_cost_text',
    type: SensorType.Summary,
    prefix: Prefix.Currency,
    converter: Converters.numberToCurrency,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Export_Income',
    mapping: 'Energy.Today.Export_Energy_Today_kWh',
    textElementId: 'energy_exported_income',
    type: SensorType.Summary,
    prefix: Prefix.Currency,
    converter: Converters.numberToCurrency,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Average,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Solar_Income',
    mapping: 'Energy.Today.PV_Energy_Today_kWh',
    textElementId: 'solar_generated_income_text',
    type: SensorType.Summary,
    prefix: Prefix.Currency,
    converter: Converters.numberToCurrency,
    forceRefresh: true,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Addition,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Battery_Details',
    mapping: 'Battery_Details',
    type: SensorType.Summary,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.All,
        singlePhaseMultipleInverters: CombinatorType.All,
        multiplePhases: CombinatorType.All
    }
}, {
    id: 'Inverter_Details',
    mapping: 'Invertor_Details',
    type: SensorType.Summary,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.All,
        singlePhaseMultipleInverters: CombinatorType.All,
        multiplePhases: CombinatorType.All
    }
}, {
    id: 'Export_Power',
    mapping: 'Power.Power.Export_Power',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Import_Power',
    mapping: 'Power.Power.Import_Power',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Meter_Import_Power',
    mapping: 'Power.Power.Meter_Import_Power',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Meter_Export_Power',
    mapping: 'Power.Power.Meter_Export_Power',
    converter: Converters.wattsToKw,
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Addition
    }
}, {
    id: 'Num_Phases',
    mapping: 'raw.invertor.num_phases',
    combinator: {
        singlePhaseSingleInverter: CombinatorType.Any,
        singlePhaseMultipleInverters: CombinatorType.Any,
        multiplePhases: CombinatorType.Any
    }
}];

export { GatewaySensors, InverterSensors };