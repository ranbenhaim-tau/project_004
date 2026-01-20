/*
  Seat selection rules
  - Available seats: blue
  - Taken: gray
  - Selected: green
  - Enforces selecting EXACTLY qty_required seats
*/

function initSeatPicker(){
  const wrap = document.querySelector('[data-seat-picker]');
  if(!wrap) return;

  const required = parseInt(wrap.getAttribute('data-qty') || '1', 10) || 1;
  const counter = document.getElementById('seat_counter');
  const btn = document.getElementById('continue_btn');

  function selectedCount(){
    return wrap.querySelectorAll('input[type="checkbox"]:checked').length;
  }

  function updateUI(){
    const count = selectedCount();
    if(counter){
      counter.textContent = `${count} / ${required} selected`;
      counter.classList.toggle('text-success', count === required);
      counter.classList.toggle('text-danger', count > required);
    }
    if(btn){
      btn.disabled = (count !== required);
    }
  }

  // prevent selecting above required
  wrap.addEventListener('change', (e)=>{
    const t = e.target;
    if(!(t instanceof HTMLInputElement)) return;
    if(t.type !== 'checkbox') return;

    const count = selectedCount();
    if(count > required){
      // undo the last action
      t.checked = false;
      updateUI();
      const toast = document.getElementById('seat_toast');
      if(toast){
        toast.textContent = `You can select up to ${required} seat(s).`;
        toast.classList.remove('d-none');
        setTimeout(()=>toast.classList.add('d-none'), 1800);
      }
      return;
    }
    updateUI();
  });

  // initial state
  updateUI();
}

window.addEventListener('DOMContentLoaded', initSeatPicker);
