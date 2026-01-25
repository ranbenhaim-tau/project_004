/*
  Search Flights UX
  - Origin: dropdown shows all origins from DB
  - Destination: dropdown depends on origin
  - Date: SimpleDatePicker enables only dates that have flights for the selected route
*/

function qs(sel){ return document.querySelector(sel); }

async function fetchJSON(url){
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if(!res.ok){ throw new Error('Request failed: ' + res.status); }
  return await res.json();
}

function setChoices(el, items, placeholder){
  if(!el) return;

  // <select>
  if((el.tagName || '').toUpperCase() === 'SELECT'){
    el.innerHTML = '';
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = placeholder || 'Select...';
    ph.selected = true;
    ph.disabled = true;
    el.appendChild(ph);

    for(const it of (items || [])){
      const opt = document.createElement('option');
      opt.value = it.code;
      opt.textContent = it.label || it.code;
      el.appendChild(opt);
    }
    return;
  }

  // Custom combo: <input> inside .airport-combo with a .airport-menu
  el.placeholder = placeholder || '';
  const wrapper = el.closest('.airport-combo');
  const menu = wrapper ? wrapper.querySelector('.airport-menu') : null;
  if(!menu){
    return;
  }

  const allItems = (items || []).map(it => ({
    code: (it.code || '').toString(),
    label: (it.label || it.code || '').toString()
  }));

  // Save for filtering
  el._airportItems = allItems;

  function closeMenu(){
    menu.style.display = 'none';
  }

  function render(list){
    menu.innerHTML = '';
    const arr = (list || []);
    if(arr.length === 0){
      closeMenu();
      return;
    }

    for(const it of arr){
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'list-group-item list-group-item-action';
      btn.textContent = it.label;
      btn.dataset.code = it.code;

      // Use mousedown so the input doesn't lose focus before we set the value
      btn.addEventListener('mousedown', (e)=>{
        e.preventDefault();
        // Show label to the user, but keep code in data-code for requests/submission.
        el.value = it.label;
        el.dataset.code = it.code;
        closeMenu();
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
      menu.appendChild(btn);
    }
    menu.style.display = 'block';
  }

  function openAll(qOverride){
    if(el.disabled) return;
    // If the input already has a selected airport, allow opening the full list
    // without forcing the user to delete the text.
    if(typeof qOverride === 'string'){
      render(filterByQuery(qOverride));
      return;
    }
    render(filterByQuery(el.value));
  }

  function filterByQuery(q){
    const query = (q || '').trim().toUpperCase();
    if(!query){
      return el._airportItems;
    }
    return el._airportItems.filter(it =>
      it.code.toUpperCase().startsWith(query) || it.label.toUpperCase().includes(query)
    );
  }

  // init event handlers once
  if(!el.dataset.comboInit){
    el.dataset.comboInit = '1';

    el.addEventListener('focus', ()=>{
      if(el.disabled) return;
      try{ el.select(); }catch(e){}
      // Always allow searching beyond the 3-letter code by keeping labels in the input.
      openAll('');
    });

    el.addEventListener('click', ()=>{
      if(el.disabled) return;
      openAll('');
    });

    el.addEventListener('input', ()=>{
      if(el.disabled) return;
      // While typing, clear stored code until user selects an item.
      delete el.dataset.code;
      render(filterByQuery(el.value));
    });

    el.addEventListener('blur', ()=>{
      // If user typed a 3-letter code (or a label) without clicking, try to resolve it.
      const raw = (el.value || '').trim();
      if(!raw) return;
      if(el.dataset.code) return;
      const q = raw.toUpperCase();
      const exactByCode = el._airportItems.find(it => it.code.toUpperCase() === q);
      if(exactByCode){
        el.value = exactByCode.label;
        el.dataset.code = exactByCode.code;
        return;
      }
      const exactByLabel = el._airportItems.find(it => it.label.toUpperCase() === q);
      if(exactByLabel){
        el.value = exactByLabel.label;
        el.dataset.code = exactByLabel.code;
      }
    });

    document.addEventListener('click', (e)=>{
      if(!wrapper.contains(e.target)){
        closeMenu();
      }
    });
  }

  // initial render (hidden until focus)
  closeMenu();
}

function disable(el, on){
  el.disabled = !!on;
  if(on) el.classList.add('disabled'); else el.classList.remove('disabled');
}

window.addEventListener('DOMContentLoaded', async ()=>{
  const originSel = qs('#origin');
  const destSel = qs('#dest');
  const dateInput = qs('#dep_date');
  const dateHint = qs('#date_hint');
  const submitBtn = qs('#search_btn');
  const form = originSel ? originSel.closest('form') : null;

  if(!originSel || !destSel || !dateInput){
    return; // not on this page
  }

  // Attach date picker
  let picker = null;
  if(window.SimpleDatePicker){
    picker = new window.SimpleDatePicker(dateInput, {
      enabledDates: [],
      minDate: new Date(),
      onSelect: ()=>{
        if(dateHint) dateHint.textContent = '';
        submitBtn && (submitBtn.disabled = false);
      }
    });
  }

  disable(destSel, true);
  disable(dateInput, true);
  if(submitBtn) submitBtn.disabled = true;

  // Load origins
  try{
    const data = await fetchJSON('/api/origins');
    setChoices(originSel, data.origins, 'Choose origin airport');
    // Prefill from server-rendered values (if present)
    const preO = (originSel.dataset.selected || '').trim();
    const preD = (destSel.dataset.selected || '').trim();
    const preDate = (dateInput.dataset.selected || '').trim();
    if(preO){
      // preO is the airport CODE from server; show label but keep code for API calls
      const hitO = (originSel._airportItems || []).find(it => it.code === preO);
      originSel.value = hitO ? hitO.label : preO;
      originSel.dataset.code = preO;
      try{
        const dd = await fetchJSON(`/api/destinations?origin=${encodeURIComponent(preO)}`);
        setChoices(destSel, dd.destinations, 'Choose destination airport');
        disable(destSel, false);
        if(preD){
          const hitD = (destSel._airportItems || []).find(it => it.code === preD);
          destSel.value = hitD ? hitD.label : preD;
          destSel.dataset.code = preD;
          disable(dateInput, true);
          if(submitBtn) submitBtn.disabled = true;
          if(dateHint) dateHint.textContent = 'Loading available dates...';
          const ad = await fetchJSON(`/api/available_dates?origin=${encodeURIComponent(preO)}&dest=${encodeURIComponent(preD)}`);
          const dates = ad.dates || [];
          if(picker){ picker.setEnabledDates(dates); }
          disable(dateInput, false);
          if(dates.length === 0){
            if(dateHint) dateHint.textContent = 'No available dates for this route.';
          }else{
            if(dateHint) dateHint.textContent = 'Blue dates are available.';
            if(preDate && dates.includes(preDate)){
              dateInput.value = preDate;
              if(submitBtn) submitBtn.disabled = false;
              if(dateHint) dateHint.textContent = '';
            }
          }
        }
      }catch(e){ console.error(e); }
    }
  }catch(e){
    console.error(e);
  }

  originSel.addEventListener('change', async ()=>{
    const o = (originSel.dataset.code || originSel.value || '').trim().toUpperCase();
    disable(destSel, true);
    disable(dateInput, true);
    if(submitBtn) submitBtn.disabled = true;
    dateInput.value = '';
    destSel.value = '';
    delete destSel.dataset.code;
    if(dateHint) dateHint.textContent = 'Choose a destination to see available dates.';

    if(!o) return;

    try{
      const data = await fetchJSON(`/api/destinations?origin=${encodeURIComponent(o)}`);
      setChoices(destSel, data.destinations, 'Choose destination airport');
      disable(destSel, false);
    }catch(e){
      console.error(e);
    }
  });

  destSel.addEventListener('change', async ()=>{
    const o = (originSel.dataset.code || originSel.value || '').trim().toUpperCase();
    const d = (destSel.dataset.code || destSel.value || '').trim().toUpperCase();
    dateInput.value = '';
    if(!o || !d) return;

    disable(dateInput, true);
    if(submitBtn) submitBtn.disabled = true;
    if(dateHint) dateHint.textContent = 'Loading available dates...';

    try{
      const data = await fetchJSON(`/api/available_dates?origin=${encodeURIComponent(o)}&dest=${encodeURIComponent(d)}`);
      const dates = data.dates || [];
      if(picker){
        picker.setEnabledDates(dates);
      }
      disable(dateInput, false);

      if(dates.length === 0){
        if(dateHint) dateHint.textContent = 'No available dates for this route.';
      }else{
        if(dateHint) dateHint.textContent = 'Blue dates are available.';
      }
    }catch(e){
      console.error(e);
      if(dateHint) dateHint.textContent = 'Could not load dates. Try again.';
    }
  });

  // Ensure the form submits airport CODES (not labels)
  if(form){
    form.addEventListener('submit', ()=>{
      if(originSel && originSel.dataset.code){ originSel.value = originSel.dataset.code; }
      if(destSel && destSel.dataset.code){ destSel.value = destSel.dataset.code; }
    });
  }
});
