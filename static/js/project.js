import '../sass/project.scss';

import {createApp} from 'vue/dist/vue.esm-bundler';
import aes from 'crypto-js/aes';
import Base64 from 'crypto-js/enc-base64';
import Utf8 from 'crypto-js/enc-utf8';
import PBKDF2 from 'crypto-js/pbkdf2';
import jsYaml from 'js-yaml';
// import like this so the JS of tabler keeps working
import Modal from 'bootstrap/js/dist/modal';

import Autocomplete from '@trevoreyre/autocomplete-js';
import ApexCharts from 'apexcharts'

import {createQueryBuilder} from './query-builder';
import Papa from 'papaparse';



export {
    createQueryBuilder
}
// TODO make the salt configurable for each centauron instance via env variable during build maybe??
const salt = Base64.parse('0tp(1rz_@f*p%=6godg!cg(4me69piwx6@-1e=6d^&xm3b^h%_');

export function encrypt(payload, key) {
    let key256Bits = PBKDF2(key, salt, {
        keySize: 256 / 32
    });
    const iv = Base64.parse(key);
    const eenc = aes.encrypt(payload, key256Bits, {iv: iv});
    return eenc.toString();
}

export function decrypt(cipher, key) {
    let key256Bits = PBKDF2(key, salt, {
        keySize: 256 / 32
    });
    const iv = Base64.parse(key);
    const dec = aes.decrypt(
        {ciphertext: Base64.parse(cipher)},
        key256Bits,
        {
            iv: iv
        });
    return Utf8.stringify(dec);
}

export function arrayEquals(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

export function isValidValue(value, type, allowedValues) {
    if (type === 'identifier') {
        return typeof value === 'string' || typeof value === 'number';
    } else if (type === 'groundtruth' || type === 'reference') {
        return allowedValues.includes(value.toString());
    }
    return false;
}


export function createTaskRun(selector, entrypoint) {
    const app = createApp({
        delimiters: ['[[', ']]'],
        data() {
            return {
                running: false,
                success: false,
                results: null,
                message: null
            };
        },
        computed: {
            groundTruth() {
                return document.getElementById('ground_truth').value;
            },
            processingResults() {
                return JSON.parse(document.getElementById('processing_results').innerText);
            },
            passphrase() {
                const el = document.getElementById('passphrase');
                return el.value;
            }
        },
        methods: {
            async run() {
                this.running = true;
                this.success = false;
                let data = null;
                if (this.passphrase.length === 0) {
                    console.warn('No passphrase given.');
                    // return;
                }
                try {
                    data = this.decrypt();
                    if (data.trim().length === 0) {
                        this.running = false;
                        this.success = false;
                        this.message = 'Encryption failed. Is the password correct?';
                        return;
                    }
                } catch (e) {
                    console.error(e);

                }
                // TODO figure out how to call entrypoint here
                // this.$nextTick(() => {
                let hiddenData = document.createElement('input');
                hiddenData.setAttribute('type', 'hidden');
                hiddenData.setAttribute('name', 'groundtruth_data');
                // hiddenData.setAttribute('value', JSON.stringify({
                //     ground_truth: data,
                //     processing_results: this.processingResults
                // }));
                hiddenData.setAttribute('value', data);

                document.querySelector('body').appendChild(hiddenData);
                this.running = false;
                this.success = true;
                this.message = 'Done.';
            },
            decrypt() {
                return decrypt(this.groundTruth, this.passphrase);
            }
        },
        async mounted() {
            await this.run();
        }
    });
    app.config.isCustomElement = tag => tag === 'py-script' || tag === 'py-config';
    app.mount(selector);
    return app;
}

// eslint-disable-next-line no-unused-vars
export function createLabelVueApp(querySelector, opts) {
    // console.log(querySelector)
    opts.csv = opts.csv || '';
    opts.encrypted = opts.encrypted || false;
    opts.validated = opts.validationResult || false;
    opts.nr_rows = opts.nr_rows || '';
    opts.nr_columns = opts.nr_columns || '';

    return createApp({
        delimiters: ['[[', ']]'],
        data() {
            return {
                message: null,
                csvformatmessage: '',
                csv: opts.csv,
                passphrase: '',
                encrypted: opts.encrypted,
                legend_text_area: '',
                validated: false,
                // nr_rows: opts.nr_rows,
                nr_columns: opts.nr_columns,
                csvSchema: ''
            };
        },
        computed: {
            schema() {
                return jsYaml.load(document.getElementById('csv_schema').value)
            },

        },
        methods: {
            getNrRows() {
                const el = document.getElementsByName('nr_rows');
                if (el.length === 1) {
                    return +el[0].value
                }
                return null;
            },
            decrypt() {
                try {
                    console.log(this.nr_rows)
                    let e = decrypt(this.csv, this.passphrase);
                    if (e.length === 0) {
                        this.message = 'Wrong passphrase?';
                        return;
                    }
                    this.csv = e;
                    this.encrypted = false;
                    this.message = 'Data decrypted';
                } catch (e) {
                    this.message = e;
                }
            },
            encrypt() {
                try {
                    this.validate()
                    this.csv = encrypt(this.csv, this.passphrase);
                    this.encrypted = true;
                    this.message = 'Data encrypted';
                } catch (e) {
                    this.message = e;
                }
            },
            validate() {
                try {
                    if (this.schema === undefined) {
                        console.warn('Schema is undefined (is it a valid yaml?)');
                        return;
                    }
                    console.log(this.csv.split('\n').length)
                    const {data: d, errors, meta} = Papa.parse(this.csv.trim(), {
                        header: true,
                        // errorOnFieldMismatch: false
                        // skipEmptyLines: true,

                    });
                    console.log(d, errors, meta);

                    if (errors.length > 0) {
                        const msg = JSON.stringify(errors);
                        this.message = msg;
                        this.validated = false;
                        throw new Error(msg);
                    }


                    const lines = this.csv.trim().split('\n');
                    const headers = lines.shift().split(',');
                    const data = lines.map(line => {
                        const values = line.split(',');
                        return headers.reduce((obj, header, index) => {
                            obj[header] = values[index];
                            return obj;
                        }, {});
                    });

                    // Check for missing columns in csv
                    const columnKeys = Object.keys(this.schema);
                    const requiredColumns = columnKeys.filter(key => this.schema[key].required);
                    const missingColumns = requiredColumns.filter(key => {
                        const colName = this.schema[key].name;
                        return !meta.fields.includes(colName);
                    });

                    if (missingColumns.length) {
                        const msg = `Missing required column(s): ${missingColumns.join(', ')}`
                        this.message = msg;
                        this.validated = false;
                        throw new Error(msg);
                    }

                    // -1 for header row
                    // nrRows is the number of files that should be contained in this ground truth.
                    const nrRows = this.getNrRows()
                    // if (lines.length !== nrRows) {
                    // more lines is fine, less lines is not
                    // TODO evaluate if this is necessary here.
                    // if (lines.length < nrRows) {
                    //     const msg = `Found rows: ${lines.length} but needed ${nrRows}`
                    //     this.message = msg;
                    //     this.validated = false;
                    //     throw new Error(msg);
                    // }

                    // Validate if data of csv is valid
                    // TODO use papaparse here as well
                    for (const key of columnKeys) {
                        const colConfig = this.schema[key];
                        const colName = colConfig.name;
                        const colType = colConfig.type;
                        console.log(colConfig)
                        let colValues = [];
                        if (colType === 'reference')
                            colValues = colConfig.values.map(e => e.toString().trim());
                        const actualColName = headers.find(e => e.trim() === colName.trim());
                        if (actualColName !== undefined) {
                            const values = data.map(row => row[actualColName]);
                            this.nr_rows = values.length;
                            for (const [index, value] of values.entries()) {
                                if (!isValidValue(value, colType, colValues)) {
                                    const lineNumber = index + 1; // Add 1 to convert from zero-based index to one-based line number
                                    throw new Error(`Value "${value}" in column "${colName}" at line ${lineNumber} is invalid. It should be one of: ${colValues.join(', ')}`);
                                }
                            }
                        }
                    }

                    this.message = 'CSV data matches the configuration described in the legend file';
                    this.validated = true;
                    return true;
                } catch (e) {
                    console.error(e)
                    this.message = e;
                    throw (e);
                }
            },
            checkCSVFormat(event) {
                const clipboardData = event.clipboardData || window.clipboardData;
                const pastedData = clipboardData.getData('text');

                // Split the pasted data into rows
                const rows = pastedData.split('\n');

                // Check if the first row contains headers separated by commas
                const headers = rows[0].trim().split(',');
                if (headers.length > 1) {
                    this.csvformatmessage = '';
                } else {
                    this.csvformatmessage = 'The data you pasted is not in CSV format.';
                }
            },
        }
    }).mount(querySelector);
}

// use this to get a modal on the template js.
// TODO figure out why exporting Modal directly in vendors.js is not working.
export function createModal(selector) {
    return Modal.getOrCreateInstance(selector);
}


export function createAutocomplete(selector, opts) {
    return new Autocomplete(selector, opts);
}

export function generateChartDataDistributionFromNodes(element, dataElement) {
    // data is in format {label:percentage}
    const data = JSON.parse(document.querySelector(dataElement).textContent);
    const labels = Object.keys(data);
    const values = Object.values(data);
    new ApexCharts(document.querySelector(element), {
        chart: {
            type: "donut",
            fontFamily: 'inherit',
            height: 240,
            sparkline: {
                enabled: true
            },
            animations: {
                enabled: false
            },
        },
        fill: {
            opacity: 1,
        },
        series: values, //[44, 55, 12, 2],
        labels: labels, //["Direct", "Affilliate", "E-mail", "Other"],
        tooltip: {
            theme: 'dark'
        },
        grid: {
            strokeDashArray: 4,
        },
        // colors: ['#00f', '#0f0', '#f00'],
        legend: {
            show: true,
            position: 'bottom',
            offsetY: 12,
            markers: {
                width: 10,
                height: 10,
                radius: 100,
            },
            itemMargin: {
                horizontal: 8,
                vertical: 8
            },
        },
        tooltip: {
            fillSeriesColor: false
        },
    }).render();
}


export function generateChartConceptDistributionByNodes(element, dataElement) {
    // data is in format {label:percentage}
    const data = JSON.parse(document.querySelector(dataElement).textContent);
    console.log(data)
    // const labels = Object.keys(data);
    // const values = Object.values(data);
    new ApexCharts(document.querySelector(element), {
        chart: {
            type: "bar",
            // fontFamily: 'inherit',
            // sparkline: {
            //     enabled: true
            // },
            height: 350,
            animations: {
                enabled: false
            },
        },
        plotOptions: {
            bar: {horizontal: false}
        },
        fill: {
            opacity: 1,
        },
        series: data, //[44, 55, 12, 2],
        // labels: labels, //["Direct", "Affilliate", "E-mail", "Other"],
        tooltip: {
            theme: 'dark'
        },
        grid: {
            strokeDashArray: 4,
        },
        // colors: ['#00f', '#0f0', '#f00'],
        legend: {
            show: true,
            position: 'bottom',
            showForSingleSeries: true,
            offsetY: 12,
            markers: {
                width: 10,
                height: 10,
                radius: 100,
            },
            itemMargin: {
                horizontal: 8,
                vertical: 8
            },
        },
        tooltip: {
            fillSeriesColor: false
        },
    }).render();
}


window.copyText = (text) => {
    if (navigator.clipboard) {
        const type = "text/plain";
        const blob = new Blob([text], {type});
        const data = [new ClipboardItem({[type]: blob})];
        navigator.clipboard.write(data);
    }
}

const formTableAction = document.querySelector('#formTableAction');
if (formTableAction != null) {
    formTableAction.addEventListener('submit', (e) => {
        // delete existing rows first
        const rows = document.querySelectorAll('#formTableAction input[name="rows"]')
        for (const r of rows) {
            formTableAction.removeChild(r);
        }

        // add a hidden input field with the id's of the select data table rows.
        for (const r of window.DT_SELECTED_ROWS) {
            const h = document.createElement('input');
            h.type = 'hidden';
            h.name = 'rows'
            h.value = r.id; // window.DT_SELECTED_ROWS.map(e => e.id).join(',');
            formTableAction.appendChild(h);
        }
    })
}
