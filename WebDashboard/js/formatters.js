class Formatters {
    /**
     * Formats a value based on the properties defined on the sensor.
     *
     * @param {any} value - The raw value from the sensor to format.
     * @param {Object} sensor - The sensor configuration object which may include converter, formatter, prefix, and suffix.
     * @param {boolean} [ignorePrefix=false] - A flag indicating whether to ignore adding the prefix.
     * @param {boolean} [ignoreSuffix=false] - A flag indicating whether to ignore adding the suffix.
     * @return {string} The formatted sensor value as a string.
     */
    static sensorValue(value, sensor, ignorePrefix = false, ignoreSuffix = false) {
        const me = this;
        let text = value;

        // Format the value if a converter function has been set
        if (sensor.converter) {
            text = sensor.converter.call(me, text);
        }

        // If the value requires other special formatting
        if (sensor.formatter) {
            text = sensor.formatter.call(me, text);
        }

        // Add any prefix
        if (sensor.prefix && !ignorePrefix) {
            text = `${sensor.prefix}${text}`;
        }

        // Add any suffix
        if (sensor.suffix && !ignoreSuffix) {
            text = `${text}${sensor.suffix}`;
        }

        return text;
    }

    static roundToOneDecimalPlace(value) {
        if(isNaN(value)) {
            value = 0.0;
        }

        return value.toFixed(1);
    }

    static roundToWholeNumber(value) {
        if(isNaN(value)) {
            value = 0.0;
        }

        return value.toFixed(0);
    }

    static renderLargeNumber(value) {
        if(isNaN(value)) {
            value = 0.0;
        }

        return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }
}

export { Formatters };