function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function formatDateTime(data) {
    return luxon.DateTime.fromISO(data).toLocaleString(luxon.DateTime.DATETIME_MED)
}

function dataTable(selector, url, opts, cb_select = null, cb_deselect = null) {
    if (!opts.columns) {
        opts.columns = [];
    }
    for (let c of opts.columns) {
        // set some default params if they are not set yet
        c.autoWidth = c.autoWidth || true;
        c.bSortable = c.bSortable || true;
        c.name = c.name || c.data;
        // set default for select checkbox
        if (c.className === 'select-checkbox') {
            c.orderable = false;
            c.defaultContent = '';
            c.searchable = false;
        }

        if (c.className === 'dt-control') {
            c.orderable = false;
            c.defaultContent = '';
            c.searchable = false;
        }
    }

    $.fn.dataTable.ext.classes.sPageButton = 'page-item';

    let ajaxUrl = url;
    ajaxUrl += ajaxUrl.includes('/?') ? '&' : '?'
    ajaxUrl += 'format=datatables'

    let csrftoken = getCookie('csrftoken')
    if (csrftoken === null) {
        csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    if (csrftoken === null) {
        console.error('Cannot get csrf token (tried cookie or input).');
    }
    // console.log(csrftoken)
    let defaults = {
        select: {
            style: 'multi',
            selector: 'td:first-child'
        },
        dom: "<'row'<'col-2'l><'col-6'B><'col-4'f>>" + // header row
            "<'row'<'col-sm-12'tr>>" +  // table row
            "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",// footer row
        serverSide: true,
        processing: true, // show loading spinner
        ajax: {
            url: ajaxUrl,
            type: 'post',
            headers: {
                "X-CSRFToken": csrftoken
            },
        },
        pageLength: 50,
        // buttons: [{'extend': 'colvis', columns: 'th:nth-child(n+2)'}],
        buttons: ['colvis'],
        stateSave: true,
        order: [[1, 'desc']],
    };
    const fullRowLink = opts.fullRowLink || true;
    delete opts.fullRowLink;
    opts = {...defaults, ...opts};
    console.log(opts)

    const dt = new DataTable(selector, opts);
    dt.buttons().container().prependTo('#toggleColumns');
    window.table = dt;
    $('#table tbody').on('click', 'tr', function (e) {
        if (fullRowLink) {
            console.log(e)
            // if (e.target.hasOwnProperty('_DT_CellIndex') && e.target['_DT_CellIndex'].column !== 0 && !e.target.classList.contains('dt-control')) { // do not fire if clicked on select box
            if (e.target.hasOwnProperty('_DT_CellIndex') && !e.target.classList.contains('dt-control')) { // do not fire if clicked on select box
                const data = dt.row(this).data();
                window.location = data.href;
            }
        }
    });
    $('div.dataTables_filter input', dt.table().container()).focus();

    window.DT_SELECTED_ROWS = [];

    $('#table').on('select.dt', (e, dt, type, indexes) => {
        if (type === 'row') {
            const rows = table.rows(indexes);
            const data = rows.data();
            rows.every(function(e) {
                let d = this.data();
                window.DT_SELECTED_ROWS.push(d);
            })
            if (cb_select != null) {
                cb_select(data)
            }
        }
    })
    $('#table').on('deselect.dt', (e, dt, type, indexes) => {
        if (type === 'row') {
            let rows = table.rows(indexes);
            const data = rows.data();
            rows.every(function(e) {
                let d = this.data();
                // let's assume we always have a column id
                window.DT_SELECTED_ROWS = window.DT_SELECTED_ROWS.filter(e => e['id'] !== d['id']);
            })
            if (cb_deselect != null) {
                cb_deselect(data)
            }
        }
    })


    return dt;
}

//
// $(document).ready(function () {
//     const button = document.querySelector('#button-import-form');
//     const tooltip = document.querySelector('#import-form');
//
//     function update() {
//         window.FloatingUIDOM.computePosition(button, tooltip).then(({x, y}) => {
//             console.log('update')
//             Object.assign(tooltip.style, {
//                 left: `${x}px`,
//                 top: `${y}px`,
//             });
//         });
//     }
//
//     function showTooltip() {
//         const display = tooltip.style.display;
//         if (display === '') {
//             tooltip.style.display = 'block';
//             update();
//         }
//         else {
//             tooltip.style.display = '';
//         }
//     }
//
//     button.addEventListener('click', showTooltip)
// });

// https://stackoverflow.com/questions/10420352/converting-file-size-in-bytes-to-human-readable-string
/**
 * Format bytes as human-readable text.
 *
 * @param bytes Number of bytes.
 * @param si True to use metric (SI) units, aka powers of 1000. False to use
 *           binary (IEC), aka powers of 1024.
 * @param dp Number of decimal places to display.
 *
 * @return Formatted string.
 */
function humanFileSize(bytes, si = false, dp = 1) {
    const thresh = si ? 1000 : 1024;

    if (Math.abs(bytes) < thresh) {
        return bytes + ' B';
    }

    const units = si
        ? ['kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
        : ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
    let u = -1;
    const r = 10 ** dp;

    do {
        bytes /= thresh;
        ++u;
    } while (Math.round(Math.abs(bytes) * r) / r >= thresh && u < units.length - 1);


    return bytes.toFixed(dp) + ' ' + units[u];
}
