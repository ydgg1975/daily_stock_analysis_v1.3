import type React from 'react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/common';

const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  // Set page title
  useEffect(() => {
    document.title = '页面未找到 - WolfyStock';
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <section className="theme-panel-glass w-full max-w-2xl px-6 py-10 text-center sm:px-10">
        <p className="label-uppercase text-secondary-text">Navigation State</p>
        <p className="mt-4 text-7xl font-normal tracking-[0.18em] text-foreground sm:text-8xl">404</p>
        <h1 className="mt-5 text-2xl font-normal tracking-[0.08em] text-foreground">页面未找到</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-secondary-text">
          当前地址不存在或已经迁移。返回首页后，可以继续进入研究、问股、持仓或回测工作区。
        </p>
        <div className="mt-8 flex justify-center">
          <Button type="button" onClick={() => navigate('/')}>
            返回首页
          </Button>
        </div>
      </section>
    </main>
  );
};

export default NotFoundPage;
