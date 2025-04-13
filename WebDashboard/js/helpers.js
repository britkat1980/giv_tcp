import {InverterSensors} from "./sensors.js";

class Helpers {
    /**
     * Traverses a nested object by processing a dot-delimited string
     * @param obj The object to traverse
     * @param mapping The mapping (a dot-delimited string)
     * @returns {*} The value of the nested object
     */
    static getPropertyValueFromMapping(obj, mapping) {
        // Mapping could be a single string, or an array of strings (where we need to find a mapping that exists).
        // This is because the mappings may differ between GivTCP v2 and v3, so we need to search multiple possible mappings.
        const mappings = Array.isArray(mapping) ? mapping : [mapping];

        for (const map of mappings) {
            let currentObj = obj;
            const properties = map.split('.');

            for (const property of properties) {
                if (currentObj && property in currentObj) {
                    currentObj = currentObj[property];
                } else {
                    currentObj = undefined;
                    break;
                }
            }

            if (currentObj !== undefined) {
                return currentObj;
            }
        }

        return undefined;
    }

    /**
     * Extracts battery objects and returns the batteries in an array.
     * Filters out any properties under the `batteries` collection that aren't an object
     * (e.g. strings `BMS_Temperature` and `BMS_Voltage`).
     * @param batteries The raw batteries object from the inverter
     * @returns {*[]} The filtered array of batteries
     */
    static getBatteriesFromInverter(batteries) {
        const filtered = {};
        let batteriesObject = batteries;

        // GivTCP v3 added the batteries under a nested object called `Battery_Stack_1`
        if (typeof batteries.Battery_Stack_1 !== 'undefined') {
            batteriesObject = batteries.Battery_Stack_1;
        }

        Object.keys(batteriesObject).forEach(key => {
            if (typeof batteriesObject[key] === 'object'
                && batteriesObject[key] !== null
                && batteriesObject[key].Battery_SOC) {
                filtered[key] = batteriesObject[key];
            }
        });

        return Object.keys(filtered).map(function(key) {
            return filtered[key];
        });
    }

    /**
     * Retrieves a sensor object by its unique identifier.
     *
     * @param {string} id - The unique identifier of the sensor to retrieve.
     * @return {Object|undefined} The sensor object matching the id, or undefined if not found.
     */
    static getSensorById(id) {
        return InverterSensors.find(sensor => sensor.id === id);
    }

    /**
     * Checks whether the provided inverter data corresponds to a 3-phase inverter.
     *
     * @param {Object} inverter - The inverter data to analyse.
     * @return {Boolean} Returns `true` if the inverter is detected as 3-phase, otherwise `false`.
     */
    static isThreePhaseInverter(inverter) {
        // First, check if the number of phases is set to 3 in the data.
        const phases = this.getPropertyValueFromMapping(inverter.data, 'raw.invertor.num_phases');

        if (phases === 3) {
            return true;
        }

        // `num_phases` can still be zero in GivTCP when we are dealing with a 3-phase inverter,
        // so attempt to fix that here by also checking the raw model name (it may contain "3ph").
        const rawModel = this.getPropertyValueFromMapping(inverter.data, 'raw.invertor.model');
        let inverterType = null;

        // Raw model name may not be helpful - also check the inverter type (description)
        if (inverter.serialNumber !== null) {
            inverterType = this.getPropertyValueFromMapping(inverter.data, `${inverter.serialNumber}.Invertor_Type`);
        }

        if ((typeof rawModel === 'string' && rawModel.includes('3ph'))
            || (typeof inverterType === 'string' && inverterType.includes('3ph'))) {
            return true;
        }

        return false;
    }
}

export { Helpers };