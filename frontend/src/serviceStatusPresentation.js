export function serviceStatusPresentation(status, isAvailable) {
  if (status === undefined && typeof isAvailable === 'boolean') {
    return isAvailable
      ? { label: 'ONLINE', dotClass: 'bg-green-400 animate-pulse', textClass: 'text-green-400' }
      : { label: 'OFFLINE', dotClass: 'bg-red-400', textClass: 'text-red-400' };
  }
  const states = {
    configured_unverified: {
      label: 'CONFIGURED · UNVERIFIED', dotClass: 'bg-yellow-400', textClass: 'text-yellow-400'
    },
    paused: { label: 'PAUSED', dotClass: 'bg-yellow-400', textClass: 'text-yellow-400' },
    unavailable: { label: 'NOT CONFIGURED', dotClass: 'bg-gray-400', textClass: 'text-gray-400' }
  };
  return typeof status === 'string' && Object.prototype.hasOwnProperty.call(states, status) ? states[status] : {
    label: 'UNKNOWN', dotClass: 'bg-gray-400', textClass: 'text-gray-400'
  };
}
