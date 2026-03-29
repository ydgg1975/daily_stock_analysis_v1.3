import { useEffect, useRef, useState } from 'react';

type ElementSize = {
  width: number;
  height: number;
};

const DEFAULT_SIZE: ElementSize = { width: 0, height: 0 };

export const useElementSize = <T extends HTMLElement>() => {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState<ElementSize>(DEFAULT_SIZE);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return undefined;
    }

    const update = (width: number, height: number) => {
      if (width > 0 && height >= 0) {
        setSize({ width, height });
      }
    };

    update(node.clientWidth, node.clientHeight);

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      update(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(node);

    return () => {
      observer.disconnect();
    };
  }, []);

  return { ref, size };
};
