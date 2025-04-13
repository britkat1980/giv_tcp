class Converters {
    /**
     * Converts Watts to Kw and returns a value to 2 decimal places
     * @param str The value to convert in Watts
     * @returns {string} Converted value in kW
     */
    static wattsToKw(str) {
        let value = parseFloat(str);

        value = (value / 1000).toFixed(2);

        return value;
    }

    /**
     * Converts a number to currency format and returns a value to 2 decimal places
     * @param str The value to convert
     * @returns {string} Converted currency value to 2 decimal places
     */
    static numberToCurrency(str) {
        if(isNaN(parseFloat(str))) {
            str = 0.0;
        }

        let value = parseFloat(str);

        value = value.toFixed(2);

        return value;
    }
}

export { Converters };