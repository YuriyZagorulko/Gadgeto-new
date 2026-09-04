'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';
import { useCartStore, useCartTotalItems, useCartSubtotal } from '@/lib/cart-store';
import { getCities, getWarehouses, getStreets } from '@/lib/api';
import type { NPCity, NPWarehouse, NPStreet } from '@/lib/api';

interface SelectedCity { ref: string; name: string; }
interface SelectedBranch { ref: string; number: string; address: string; }
interface SelectedStreet { ref: string; name: string; }

type DeliveryMethod = 'warehouse' | 'courier';
type PaymentMethod = 'cod' | 'liqpay' | 'bank_transfer';

const LIQPAY_CHECKOUT_URL = 'https://www.liqpay.ua/api/3/checkout';

export default function CheckoutPage() {
  const t = useTranslations('checkout');
  const locale = useLocale();
  const router = useRouter();
  const items = useCartStore((s) => s.items);
  const sessionToken = useCartStore((s) => s.sessionToken);
  const refreshFromAPI = useCartStore((s) => s.refreshFromAPI);
  const totalItems = useCartTotalItems();
  const subtotal = useCartSubtotal();
  const [form, setForm] = useState({first_name:'',last_name:'',phone:'',email:'',notes:''});
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Payment method
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cod');

  // "warehouse" — відділення/поштомат, "courier" — адресна (кур'єрська) доставка
  const [deliveryMethod, setDeliveryMethod] = useState<DeliveryMethod>('warehouse');

  // Nova Poshta city selection
  const [city, setCity] = useState<SelectedCity | null>(null);
  const [cityInput, setCityInput] = useState('');
  const [cityOptions, setCityOptions] = useState<NPCity[]>([]);
  const [citiesOpen, setCitiesOpen] = useState(false);
  const [citiesLoading, setCitiesLoading] = useState(false);
  const [cityError, setCityError] = useState('');

  // Nova Poshta branch (warehouse) selection
  const [branch, setBranch] = useState<SelectedBranch | null>(null);
  const [branchInput, setBranchInput] = useState('');
  const [branchOptions, setBranchOptions] = useState<NPWarehouse[]>([]);
  const [branchesOpen, setBranchesOpen] = useState(false);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [branchError, setBranchError] = useState('');
  const branchInputRef = useRef<HTMLInputElement>(null);

  // Nova Poshta courier address (street + building + apartment)
  const [street, setStreet] = useState<SelectedStreet | null>(null);
  const [streetInput, setStreetInput] = useState('');
  const [streetOptions, setStreetOptions] = useState<NPStreet[]>([]);
  const [streetsOpen, setStreetsOpen] = useState(false);
  const [streetsLoading, setStreetsLoading] = useState(false);
  const [streetError, setStreetError] = useState('');
  const [building, setBuilding] = useState('');
  const [apartment, setApartment] = useState('');
  const streetInputRef = useRef<HTMLInputElement>(null);
  const buildingInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    refreshFromAPI().then(() => setLoaded(true)).catch(() => setLoaded(true));
  }, [refreshFromAPI]);

  // Debounced city search against the NP API
  useEffect(() => {
    if (!citiesOpen) return;
    const query = cityInput.trim();
    if (city && query === city.name) return;
    if (query.length < 2) { setCityOptions([]); return; }
    const timer = setTimeout(() => {
      setCitiesLoading(true);
      setCityError('');
      getCities(query)
        .then((data) => {
          if (data.error) { setCityOptions([]); setCityError(data.error); }
          else setCityOptions(data.items);
        })
        .catch(() => { setCityOptions([]); setCityError(t('searchError')); })
        .finally(() => setCitiesLoading(false));
    }, 350);
    return () => clearTimeout(timer);
  }, [cityInput, citiesOpen, city, t]);

  const selectCity = useCallback((c: NPCity) => {
    setCity({ ref: c.ref, name: c.name });
    setCityInput(c.name);
    setCitiesOpen(false);
    setCityOptions([]);
    // Reset downstream selections when city changes
    setBranch(null); setBranchInput(''); setBranchOptions([]); setBranchesOpen(false);
    setStreet(null); setStreetInput(''); setStreetOptions([]); setStreetsOpen(false);
    setBuilding(''); setApartment('');
  }, []);

  // Debounced branch search
  useEffect(() => {
    if (!branchesOpen || !city) return;
    const query = branchInput.trim();
    if (branch && query === branch.number) return;
    if (query.length < 2) { setBranchOptions([]); return; }
    const timer = setTimeout(() => {
      setBranchesLoading(true);
      setBranchError('');
      getWarehouses(city.ref, query)
        .then((data) => {
          if (data.error) { setBranchOptions([]); setBranchError(data.error); }
          else setBranchOptions(data.items);
        })
        .catch(() => { setBranchOptions([]); setBranchError(t('searchError')); })
        .finally(() => setBranchesLoading(false));
    }, 350);
    return () => clearTimeout(timer);
  }, [branchInput, branchesOpen, city, branch, t]);

  const selectBranch = useCallback((b: NPWarehouse) => {
    setBranch({ ref: b.ref, number: b.number, address: b.address });
    setBranchInput(`№${b.number} — ${b.short_address || b.address}`);
    setBranchesOpen(false);
    setBranchOptions([]);
  }, []);

  // Debounced street search
  useEffect(() => {
    if (!streetsOpen || !city) return;
    const query = streetInput.trim();
    if (street && query === street.name) return;
    if (query.length < 2) { setStreetOptions([]); return; }
    const timer = setTimeout(() => {
      setStreetsLoading(true);
      setStreetError('');
      getStreets(city.ref, query)
        .then((data) => {
          if (data.error) { setStreetOptions([]); setStreetError(data.error); }
          else setStreetOptions(data.items);
        })
        .catch(() => { setStreetOptions([]); setStreetError(t('searchError')); })
        .finally(() => setStreetsLoading(false));
    }, 350);
    return () => clearTimeout(timer);
  }, [streetInput, streetsOpen, city, street, t]);

  const selectStreet = useCallback((s: NPStreet) => {
    const label = s.street_type ? `${s.street_type} ${s.name}` : s.name;
    setStreet({ ref: s.ref, name: label });
    setStreetInput(label);
    setStreetsOpen(false);
    setStreetOptions([]);
    setTimeout(() => buildingInputRef.current?.focus(), 50);
  }, []);

  // Reset branch/street selections when delivery method changes
  useEffect(() => {
    if (!city) return;
    setBranch(null); setBranchInput(''); setBranchOptions([]); setBranchesOpen(false);
    setStreet(null); setStreetInput(''); setStreetOptions([]); setStreetsOpen(false);
    setBuilding(''); setApartment('');
  }, [deliveryMethod, city]);

  const deliveryReady = (): boolean => {
    if (!city) return false;
    if (deliveryMethod === 'warehouse') return !!branch;
    return !!street && !!building.trim();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setSubmitting(true);
    const token = localStorage.getItem('auth_token');
    try {
      if (!city) { setError(t('selectCityFirst')); setSubmitting(false); return; }
      if (deliveryMethod === 'warehouse' && !branch) { setError(t('selectCityAndBranch')); setSubmitting(false); return; }
      if (deliveryMethod === 'courier' && (!street || !building.trim())) { setError(t('selectCityAndStreet')); setSubmitting(false); return; }

      const res = await fetch('/api/checkout', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          session_token: sessionToken||'',
          first_name: form.first_name, last_name: form.last_name,
          phone: form.phone, email: form.email,
          city_ref: city.ref, city_name: city.name,
          warehouse_ref: branch?.ref || '', warehouse_number: branch?.number || '',
          delivery_method: deliveryMethod,
          street_ref: street?.ref || '', street_name: street?.name || '',
          building, apartment,
          delivery_address: deliveryMethod === 'warehouse'
            ? (branch ? `№${branch.number}, ${branch.address}` : '')
            : `${city.name}, ${street?.name || ''} ${building}${apartment ? ', кв. ' + apartment : ''}`,
          payment_method: paymentMethod,
          notes: form.notes,
          auth_token: token||'',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Checkout failed');

      localStorage.setItem('last_order', JSON.stringify(data));

      // LiqPay: auto-submit the payment form
      if (data.payment_method === 'liqpay' && data.payment) {
        const formEl = document.createElement('form');
        formEl.method = 'POST';
        formEl.action = LIQPAY_CHECKOUT_URL;
        formEl.style.display = 'none';
        const addField = (name: string, val: string) => {
          const inp = document.createElement('input'); inp.type = 'hidden'; inp.name = name; inp.value = val; formEl.appendChild(inp);
        };
        addField('data', data.payment.data);
        addField('signature', data.payment.signature);
        addField('public_key', data.payment.public_key);
        document.body.appendChild(formEl);
        formEl.submit();
        return;
      }

      router.push('/checkout/success?order_id='+data.order_id);
    } catch (err:any) { setError(err.message); setSubmitting(false); }
  };

  if (!loaded) return <div className="p-8 text-center">{t('processing')}</div>;
  if (!items.length) return <div className="p-8 text-center">{t('emptyCart')}</div>;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">{t('title')}</h1>
      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column: customer info + delivery */}
        <div className="lg:col-span-2 space-y-6">
          {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div className="card p-6 space-y-4">
            <h2 className="font-semibold">{t('customerInfo')}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="block text-sm font-medium mb-1">{t('firstName')}</label><input type="text" value={form.first_name} onChange={e=>setForm({...form,first_name:e.target.value})} className="input-field" required /></div>
              <div><label className="block text-sm font-medium mb-1">{t('lastName')}</label><input type="text" value={form.last_name} onChange={e=>setForm({...form,last_name:e.target.value})} className="input-field" required /></div>
            </div>
            <div><label className="block text-sm font-medium mb-1">{t('phone')}</label><input type="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} className="input-field" required /></div>
            <div><label className="block text-sm font-medium mb-1">{t('email')}</label><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="input-field" required /></div>
          </div>

          <div className="card p-6 space-y-4">
            <h2 className="font-semibold">{t('delivery')}</h2>

            {/* Delivery method toggle */}
            <div className="flex gap-2">
              <button type="button" onClick={() => setDeliveryMethod('warehouse')} className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${deliveryMethod === 'warehouse' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:border-gray-400'}`}>{t('deliveryBranch')}</button>
              <button type="button" onClick={() => setDeliveryMethod('courier')} className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${deliveryMethod === 'courier' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:border-gray-400'}`}>{t('deliveryCourier')}</button>
            </div>

            {/* City search */}
            <div className="relative">
              <label className="block text-sm font-medium mb-1">{t('city')}</label>
              <input type="text" value={cityInput} placeholder={t('cityPlaceholder')} autoComplete="off" onFocus={() => setCitiesOpen(true)} onChange={(e) => { setCityInput(e.target.value); setCitiesOpen(true); if (city) setCity(null); }} className="input-field" />
              {cityError && <p className="text-xs text-red-600 mt-1">{cityError}</p>}
              {citiesOpen && (
                <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                  {citiesLoading && <div className="p-3 text-sm text-gray-500">{t('searching')}</div>}
                  {!citiesLoading && cityOptions.length === 0 && <div className="p-3 text-sm text-gray-500">{t('noCitiesFound')}</div>}
                  {!citiesLoading && cityOptions.map((c) => (
                    <button type="button" key={c.ref} onClick={() => selectCity(c)} className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50">
                      <span className="font-medium">{c.name}</span>
                      {c.area && <span className="text-gray-400 ml-2">{c.area}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {deliveryMethod === 'warehouse' && (
              <div className="relative">
                <label className="block text-sm font-medium mb-1">{t('branch')}</label>
                <input ref={branchInputRef} type="text" value={branchInput} disabled={!!(citiesOpen && cityOptions.length > 0)} placeholder={!city ? t('selectCityFirst') : t('branchPlaceholder')} autoComplete="off" onFocus={() => { if (city) setBranchesOpen(true); }} onChange={(e) => { setBranchInput(e.target.value); setBranchesOpen(true); if (branch) setBranch(null); }} className="input-field disabled:bg-gray-100 disabled:cursor-not-allowed" />
                {branchError && <p className="text-xs text-red-600 mt-1">{branchError}</p>}
                {branchesOpen && city && (
                  <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                    {branchesLoading && <div className="p-3 text-sm text-gray-500">{t('searching')}</div>}
                    {!branchesLoading && branchOptions.length === 0 && <div className="p-3 text-sm text-gray-500">{t('noBranchesFound')}</div>}
                    {!branchesLoading && branchOptions.map((b) => (
                      <button type="button" key={b.ref} onClick={() => selectBranch(b)} className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50">
                        <span className="font-medium">№{b.number}</span>
                        <span className="text-gray-500 ml-2">{b.short_address || b.address}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {deliveryMethod === 'courier' && (
              <div className="space-y-4">
                <div className="relative">
                  <label className="block text-sm font-medium mb-1">{t('street')}</label>
                  <input ref={streetInputRef} type="text" value={streetInput} disabled={!!(citiesOpen && cityOptions.length > 0)} placeholder={!city ? t('selectCityFirst') : t('streetPlaceholder')} autoComplete="off" onFocus={() => { if (city) setStreetsOpen(true); }} onChange={(e) => { setStreetInput(e.target.value); setStreetsOpen(true); if (street) setStreet(null); }} className="input-field disabled:bg-gray-100 disabled:cursor-not-allowed" />
                  {streetError && <p className="text-xs text-red-600 mt-1">{streetError}</p>}
                  {streetsOpen && city && (
                    <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                      {streetsLoading && <div className="p-3 text-sm text-gray-500">{t('searching')}</div>}
                      {!streetsLoading && streetOptions.length === 0 && <div className="p-3 text-sm text-gray-500">{t('noStreetsFound')}</div>}
                      {!streetsLoading && streetOptions.map((s) => (
                        <button type="button" key={s.ref} onClick={() => selectStreet(s)} className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50">
                          {s.street_type ? `${s.street_type} ` : ''}{s.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('building')}</label>
                    <input ref={buildingInputRef} type="text" value={building} onChange={(e) => setBuilding(e.target.value)} disabled={!city} className="input-field disabled:bg-gray-100 disabled:cursor-not-allowed" placeholder={t('buildingPlaceholder')} autoComplete="off" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('apartment')}</label>
                    <input type="text" value={apartment} onChange={(e) => setApartment(e.target.value)} disabled={!city} className="input-field disabled:bg-gray-100 disabled:cursor-not-allowed" placeholder={t('apartmentPlaceholder')} autoComplete="off" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="card p-6 space-y-4">
            <label className="block text-sm font-medium mb-1">{t('notes')}</label>
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input-field" rows={3} placeholder={t('notesPlaceholder')} />
          </div>
        </div>

        {/* Right column: order summary + payment */}
        <div className="lg:col-span-1 space-y-6">
          <div className="card p-6 space-y-4 lg:sticky lg:top-4">
            <h2 className="font-semibold">{t('yourOrder')}</h2>
            <ul className="divide-y divide-gray-100 max-h-64 overflow-auto">
              {items.map((item) => (
                <li key={item.product_id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                  <Link href={`/product/${item.slug}`} target="_blank" rel="noopener noreferrer" className="w-14 h-14 flex-shrink-0 rounded-md overflow-hidden bg-gray-100 hover:opacity-80 transition-opacity">
                    {item.image ? (
                      <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-400">{t('noImage')}</div>
                    )}
                  </Link>
                  <div className="flex-1 min-w-0">
                    <Link href={`/product/${item.slug}`} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-800 line-clamp-2 hover:text-blue-600 transition-colors">{item.name}</Link>
                    {item.sku && <div className="text-xs text-gray-400 mt-0.5">{item.sku}</div>}
                    <div className="text-sm text-gray-500 mt-1">{item.qty} {t('qtyUnit')} × {formatPrice(item.price, locale)}</div>
                  </div>
                  <div className="text-sm font-semibold flex-shrink-0 text-right">{formatPrice(item.qty * item.price, locale)}</div>
                </li>
              ))}
            </ul>

            <div className="border-t border-gray-100 pt-4 space-y-3">
              <h3 className="text-sm font-semibold">{t('paymentMethod')}</h3>
              <div className="space-y-2">
                {([['cod', t('paymentCod'), t('paymentCodDesc')], ['liqpay', t('paymentLiqpay'), t('paymentLiqpayDesc')], ['bank_transfer', t('paymentBank'), t('paymentBankDesc')]] as [PaymentMethod, string, string][]).map(([value, label, desc]) => (
                  <label key={value} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${paymentMethod === value ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                    <input type="radio" name="payment_method" value={value} checked={paymentMethod === value} onChange={() => setPaymentMethod(value)} className="mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{label}</div>
                      <div className="text-xs text-gray-500">{desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="border-t border-gray-100 pt-4 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">{t('subtotal')}</span><span>{formatPrice(subtotal, locale)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">{t('shipping')}</span><span className="text-green-600">{t('freeShipping')}</span></div>
              <div className="flex justify-between text-lg font-bold pt-2 border-t border-gray-100"><span>{t('totalLabel')}</span><span>{formatPrice(subtotal, locale)}</span></div>
            </div>

            <button type="submit" disabled={submitting} className="btn-primary w-full text-lg">{submitting ? t('processing') : t('placeOrder')}</button>
          </div>
        </div>
      </form>
    </div>
  );
}
