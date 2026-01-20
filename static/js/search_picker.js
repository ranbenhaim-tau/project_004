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
        el.value = it.code;
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
      render(filterByPrefix(qOverride));
      return;
    }
    render(filterByPrefix(el.value));
  }

  function filterByPrefix(q){
    const query = (q || '').trim().toUpperCase();
    if(!query){
      return el._airportItems;
    }
    return el._airportItems.filter(it =>
      it.code.toUpperCase().startsWith(query) || it.label.toUpperCase().startsWith(query)
    );
  }

  // init event handlers once
  if(!el.dataset.comboInit){
    el.dataset.comboInit = '1';

    el.addEventListener('focus', ()=>{
      if(el.disabled) return;
      try{ el.select(); }catch(e){}
      const showAll = (el.dataset.selected && el.value === el.dataset.selected);
      openAll(showAll ? '' : undefined);
    });

    el.addEventListener('click', ()=>{
      if(el.disabled) return;
      const showAll = (el.dataset.selected && el.value === el.dataset.selected);
      openAll(showAll ? '' : undefined);
    });

    el.addEventListener('input', ()=>{
      if(el.disabled) return;
      render(filterByPrefix(el.value));
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
      originSel.value = preO;
      try{
        const dd = await fetchJSON(`/api/destinations?origin=${encodeURIComponent(preO)}`);
        setChoices(destSel, dd.destinations, 'Choose destination airport');
        disable(destSel, false);
        if(preD){
          destSel.value = preD;
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
    const o = originSel.value;
    disable(destSel, true);
    disable(dateInput, true);
    if(submitBtn) submitBtn.disabled = true;
    dateInput.value = '';
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
    const o = originSel.value;
    const d = destSel.value;
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
});
