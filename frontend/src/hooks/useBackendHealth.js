import { useState, useEffect, useCallback } from 'react';
import { checkHealth } from '../services/api';

export const useBackendHealth = (pollIntervalMs = 10000) => {
  const [isOnline, setIsOnline] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState(null);

  const check = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await checkHealth();
      if (data && data.status === 'healthy') {
        setIsOnline(true);
        setHealthData(data);
      } else {
        setIsOnline(false);
      }
    } catch {
      setIsOnline(false);
      setHealthData(null);
    } finally {
      setIsLoading(false);
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    check();
    if (pollIntervalMs > 0) {
      const timer = setInterval(check, pollIntervalMs);
      return () => clearInterval(timer);
    }
  }, [check, pollIntervalMs]);

  return { isOnline, isLoading, healthData, lastChecked, refresh: check };
};

