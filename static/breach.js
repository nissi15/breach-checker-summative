//  -- tab 1: breach news
const breachSearch = document.getElementById('breach-search');
const yearSelect = document.getElementById('small-select');
const checkSort = document.getElementById('check-sort');
const breachFilters = document.querySelectorAll('#breachFilters input');
const breachMsg = document.getElementById('breach-msg');
const breachCount = document.getElementById('breachCount');
const breachTable = document.getElementById('breach-table');
const breachRows = document.getElementById('breach-rows');
const pageBtn = document.getElementById('page-btn');
const breachSearchForm = document.getElementById('breach-search-form');

const pageSize = 10;
let breaches = [];
let currentPage = 1;
let openBreachName = '';


const infoIcon = '<img class="tip-icon" src="/static/images/info.png" alt="">';

async function loadBreaches() {
    try {
        const data = await askServer('/api/breaches', 'GET');
        breaches = data.breaches;

        if (data.source === 'old-cache') {
            showMessage(breachMsg, 'Showing saved data. The breach service is not answering right now.', 'warning');
        }

        fillYears();
        renderBreaches();
    } catch (error) {
        breachCount.textContent = '';
        showMessage(breachMsg, error.message, 'error');
    }
}

function fillYears() {
    const years = [];
    
    for (let i = 0; i < breaches.length; i += 1) {
        const year = breaches[i].added.slice(0, 4);

        if (!years.includes(year)) {
            years.push(year)
        }
    } 

    years.sort();
    years.reverse();

    for (let i=0; i < years.length; i += 1) {
        const option = document.createElement('option');
            option.value = years[i];
            option.textContent = years[i];
            yearSelect.appendChild(option);
    }
}


// finding breaches in search
function breachMatching(breach, searchTxt, year, ticked) {
    const nameTxt = (breach.name + ' ' + breach.domain).toLowerCase();

    if (searchTxt !== '' && !nameTxt.includes(searchTxt)) return false;
    if (year !== 'all' && !breach.added.startsWith(year)) return false;

    for (let i = 0; i < ticked.length; i += 1) {
        if (ticked[i] === 'verified') {
            if (!breach.verified) return false;
        } else if (!breach.data.includes(ticked[i])) {
            return false;
        }
    }
    return true;
}

function getVisibleBreaches() {
    const searchTxt = breachSearch.value.trim().toLowerCase();
    const year = yearSelect.value;
    const sortField = checkSort.value;

    const ticked = [];
    for(let i = 0; i < breachFilters.length; i += 1) {
        if (breachFilters[i].checked) {
            ticked.push(breachFilters[i].value);
        }
    }

    const visibleBreaches = breaches.filter(function (breach) {
        return breachMatching(breach, searchTxt, year, ticked);
    });

    visibleBreaches.sort(function (FirstBreach, secondBreach) {
        if (sortField === 'biggest') {
            return secondBreach.count - firstBreach.count;
        } else if (sortField === 'newest') {
            return secondBreach.added.localeCompare(firstBreach.added);
        } else if (sortField === '0ldest') {
            return firstBreach.added.localeCompare(secondBreach.added);
        } else {
            return firstBreach.name.localeCompare(secondBreach.name);
        }
    });
    return visibleBreaches;
}


function formatDate(dateTxt) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const dateParts = dateTxt.split('-');
    const year = dateParts[0];
    const month = months[Number(dateParts[1]) - 1];
    const day = Number(dateParts[2]);

    return day + ' ' + month + ' ' + year;
}

// a short safety tip based on what leaked
function makeTip(breach) {
    if (breach.data.includes('Passwords')) {
        return 'Passwords were leaked here. Use a unique password.';
    } else if (breach.data.includes('Phone numbers')) {
        return 'Phone numbers were leaked here. Watch out for scam calls and sms.';
    } else if (breach.data.includes('Email addresses')) {
        return 'Emails were leaked here. Be careful with scam emails .';
    } else {
        return 'Consider what personal details you give this website.';
    }
}


function shortName(dataType) {
    if (dataType === 'Email addresses') return 'Emails';
    if (dataType === 'Geographic locations') return 'Locations';
    return dataType;
}


function makePills(breach) {
    let pills = '';

    for (let i = 0; i < breach.data.length && i < 3; i += 1) {
        pills += '<span class="data-pill">' + tweakSpecialHtml(shortName(breach.data[i])) + '</span>';
    }

    if (breach.data.length > 3) {
        pills += '<span class="data-pill">+' + (breach.data.length - 3) + '</span>';
    }

    return pills;
}


function makeBreachRow(breach) {
    const name = tweakSpecialHtml(breach.name);
    const isOpen = openBreachName === breach.name;
    const arrow = isOpen ? '&darr;' : '&rarr;';

    let row = '<tr class="breach-row' + (isOpen ? ' open' : '') + '" data-name="' + name + '">' +
        '<td class="breach-name">' + name + '</td>' +
        '<td>' + formatDate(breach.added) + '</td>' +
        '<td>' + formatShort(breach.count) + '</td>' +
        '<td><div class="data-pills">' + makePills(breach) + '</div></td>' +
        '<td class="arrow-cell">' + arrow + '</td>' +
        '</tr>';

    if (isOpen) {
        
        let checkLink = '';
        if (breach.data.includes('Passwords')) {
            checkLink = '<button class="tip-link" type="button">Check your password &rarr;</button>';
        }

        const allData = [];
        for (let i = 0; i < breach.data.length; i += 1) {
            allData.push(shortName(breach.data[i]));
        }

        row += '<tr class="tip-row" data-name="' + name + '"><td colspan="5">' +
            '<p class="breach-tip">' + infoIcon +
            '<span><strong>' + tweakSpecialHtml(breach.domain || breach.name) + '</strong> was breached in ' +
            breach.date.slice(0, 4) + ' and leaked: ' +
            tweakSpecialHtml(allData.join(', ')) + '. ' + tweakSpecialHtml(makeTip(breach)) + '</span>' +
            checkLink + '</p></td></tr>';
    }

    return row;
}

function renderBreaches() {
    const visibleBreaches = getVisibleBreaches();
    let totalPages = Math.ceil(visibleBreaches.length / pageSize);

    if (totalPages < 1) totalPages = 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start = (currentPage - 1) * pageSize;
    const pageBreaches = visibleBreaches.slice(start, start + pageSize);

    if (visibleBreaches.length === 0) {
        breachCount.textContent = 'No websites match your search.';
    } else {
        breachCount.textContent = 'Showing ' + (start + 1) + '–' + (start + pageBreaches.length) +
            ' of ' + formatNumber(visibleBreaches.length) + ' breached sites';
    }

    let rows = '';
    for (let i = 0; i < pageBreaches.length; i += 1) {
        rows += makeBreachRow(pageBreaches[i]);
    }

    breachRows.innerHTML = rows;
    breachTable.hidden = visibleBreaches.length === 0;
    renderPageButtons(totalPages);
}

// previous, up to 5 page numbers, then Next
function renderPageButtons(totalPages) {
    let lastNbr = currentPage + 2;
    if (lastNbr < 5) lastNbr = 5;
    if (lastNbr > totalPages) lastNbr = totalPages;

    let firstNbr = lastNbr - 4;
    if (firstNbr < 1) firstNbr = 1;

    let buttons = '<button class="page-button" data-page="' + (currentPage - 1) + '"' +
        (currentPage === 1 ? ' disabled' : '') + '>Previous</button>';

    for (let nbr = firstNbr; nbr <= lastNbr; nbr += 1) {
        buttons += '<button class="page-button number' + (nbr === currentPage ? ' active' : '') +
            '" data-page="' + nbr + '">' + nbr + '</button>';
    }

    buttons += '<button class="page-button" data-page="' + (currentPage + 1) + '"' +
        (currentPage === totalPages ? ' disabled' : '') + '>Next</button>';

    pageBtn.innerHTML = buttons;
}

// searching goes back to ist page
function updateBreaches() {
    currentPage = 1;
    renderBreaches();
}

function submitBreachSearch(event) {
    event.preventDefault();
    updateBreaches();
}

function changePage(event) {
    const clickedBtn = event.target.closest('.page-button');

    if (!clickedBtn || clickedBtn.disabled) return;

    currentPage = Number(clickedBtn.getAttribute('data-page'));
    renderBreaches();
    window.scrollTo(0, 0);
}


function goToPasswordCheck() {
    showTab('share');
    window.scrollTo(0, 0);
    document.getElementById('secret-txt').focus();
}

function toggleBreachTip(event) {
    if (event.target.closest('.tip-link')) {
        goToPasswordCheck();
        return;
    }

    const clickedRow = event.target.closest('tr[data-name]');

    if (!clickedRow) return;

    const rowName = clickedRow.getAttribute('data-name');

    if (openBreachName === rowName) {
        openBreachName = '';
    } else {
        openBreachName = rowName;
    }

    renderBreaches();
}

breachSearch.addEventListener('input', updateBreaches);
yearSelect.addEventListener('change', updateBreaches);
checkSort.addEventListener('change', updateBreaches);

for (let i = 0; i < breachFilters.length; i += 1) {
    breachFilters[i].addEventListener('change', updateBreaches);
}

breachSearchForm.addEventListener('submit', submitBreachSearch);
pageBtn.addEventListener('click', changePage);
breachRows.addEventListener('click', toggleBreachTip);

