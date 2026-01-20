/*
  SimpleDatePicker
  - dependency-free
  - disabled days are gray and not clickable
  - enabled days are blue
*/

(function(){
  function pad2(n){ return String(n).padStart(2,'0'); }
  function ymd(d){ return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`; }

  function monthTitle(d){
    // Force English month names regardless of browser/OS locale.
    return d.toLocaleString('en-US', { month: 'long', year: 'numeric' });
  }

  class SimpleDatePicker {
    constructor(inputEl, opts){
      this.inputEl = inputEl;
      this.opts = opts || {};
      // Enabled-dates behavior:
      // - enabledDates is undefined/null  -> all dates enabled (subject to min/max)
      // - enabledDates is []              -> no dates enabled
      // - enabledDates is [..dates..]     -> only those dates enabled
      this._enabledMode = 'all';
      this.enabled = new Set();
      if(Array.isArray(this.opts.enabledDates)){
        if(this.opts.enabledDates.length === 0){
          this._enabledMode = 'none';
        }else{
          this._enabledMode = 'some';
          this.enabled = new Set(this.opts.enabledDates);
        }
      }
      this.minDate = this.opts.minDate || null; // Date
      this.maxDate = this.opts.maxDate || null; // Date
      this.onSelect = this.opts.onSelect || function(){};
      this.viewDate = new Date();
      this.viewDate.setDate(1);

      this._build();
      this._bind();
    }

    setEnabledDates(dates){
      if(dates == null){
        this._enabledMode = 'all';
        this.enabled = new Set();
      }else if(Array.isArray(dates) && dates.length === 0){
        this._enabledMode = 'none';
        this.enabled = new Set();
      }else{
        this._enabledMode = 'some';
        this.enabled = new Set(dates || []);
      }
      this._render();
    }

    open(){
      this.popup.classList.add('open');
      this._render();
    }

    close(){
      this.popup.classList.remove('open');
    }

    _build(){
      const pop = document.createElement('div');
      pop.className = 'dp-popup';
      pop.innerHTML = `
        <div class="dp-head">
          <button type="button" class="dp-nav" data-nav="prev" aria-label="Previous month">‹</button>
          <div class="dp-title"></div>
          <button type="button" class="dp-nav" data-nav="next" aria-label="Next month">›</button>
        </div>
        <div class="dp-week"></div>
        <div class="dp-grid"></div>
      `;

      this.popup = pop;
      // attach right after input
      const wrapper = document.createElement('div');
      wrapper.className = 'dp-wrap';
      this.inputEl.parentNode.insertBefore(wrapper, this.inputEl);
      wrapper.appendChild(this.inputEl);
      wrapper.appendChild(pop);

      const week = pop.querySelector('.dp-week');
      const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
      week.innerHTML = days.map(d=>`<div class="dp-dow">${d}</div>`).join('');
    }

    _bind(){
      this.inputEl.addEventListener('click', (e)=>{
        e.preventDefault();
        this.open();
      });

      document.addEventListener('click', (e)=>{
        if(!this.popup.classList.contains('open')) return;
        const isInside = this.popup.contains(e.target) || this.inputEl.contains(e.target);
        if(!isInside) this.close();
      });

      this.popup.addEventListener('click', (e)=>{
        const nav = e.target.closest('[data-nav]');
        if(nav){
          const dir = nav.getAttribute('data-nav');
          if(dir==='prev') this.viewDate.setMonth(this.viewDate.getMonth()-1);
          if(dir==='next') this.viewDate.setMonth(this.viewDate.getMonth()+1);
          this._render();
          return;
        }

        const dayBtn = e.target.closest('[data-date]');
        if(dayBtn && !dayBtn.classList.contains('disabled')){
          const ds = dayBtn.getAttribute('data-date');
          this.inputEl.value = ds;
          this.onSelect(ds);
          this.close();
        }
      });

      // close on Escape
      this.inputEl.addEventListener('keydown', (e)=>{
        if(e.key==='Escape') this.close();
      });
    }

    _isInRange(d){
      if(this.minDate && d < this.minDate) return false;
      if(this.maxDate && d > this.maxDate) return false;
      return true;
    }

    _render(){
      const title = this.popup.querySelector('.dp-title');
      title.textContent = monthTitle(this.viewDate);

      const grid = this.popup.querySelector('.dp-grid');
      grid.innerHTML = '';

      const year = this.viewDate.getFullYear();
      const month = this.viewDate.getMonth();

      // Monday-based index: 0..6
      const first = new Date(year, month, 1);
      let firstDow = (first.getDay() + 6) % 7; // JS Sunday=0 -> Monday=0

      const daysInMonth = new Date(year, month+1, 0).getDate();

      // previous month padding
      // (class names aligned with CSS)
      for(let i=0;i<firstDow;i++){
        const pad = document.createElement('div');
        pad.className = 'dp-day blank';
        grid.appendChild(pad);
      }

      for(let day=1; day<=daysInMonth; day++){
        const d = new Date(year, month, day);
        const ds = ymd(d);
        const cell = document.createElement('button');
        cell.type = 'button';
        cell.className = 'dp-day';
        cell.textContent = String(day);
        cell.setAttribute('data-date', ds);

        const enabled = (this._enabledMode === 'all') ? true :
                        (this._enabledMode === 'some') ? this.enabled.has(ds) :
                        false;
        const inRange = this._isInRange(d);

        if(!enabled || !inRange){
          cell.classList.add('disabled');
          cell.tabIndex = -1;
        }

        // mark selected
        if(this.inputEl.value && this.inputEl.value === ds){
          cell.classList.add('selected');
        }

        grid.appendChild(cell);
      }
    }
  }

  window.SimpleDatePicker = SimpleDatePicker;
})();
