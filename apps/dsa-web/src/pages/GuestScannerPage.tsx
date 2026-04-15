import type React from 'react';
import { BarChart3, History, Radar, ShieldAlert, TestTubeDiagonal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, WorkspacePageHeader } from '../components/common';
import { LockedFeatureCard } from '../components/access/LockedFeatureCard';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLoginPath, buildRegistrationPath } from '../hooks/useProductSurface';

const GuestScannerPage: React.FC = () => {
  const { language } = useI18n();
  const loginPath = buildLoginPath('/scanner');
  const registrationPath = buildRegistrationPath('/scanner');

  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        eyebrow={language === 'en' ? 'Scanner Preview' : '扫描器预告'}
        title={language === 'en' ? 'Market Scanner Teaser' : 'Market Scanner 预告'}
        description={language === 'en'
          ? 'Guests can inspect the scanner workflow and product boundaries, but manual runs, watchlists, and review history unlock only after sign-in.'
          : '游客可以先了解扫描器的工作方式与产品边界，但手动运行、观察名单与复盘历史需要登录后解锁。'}
        actions={(
          <Link
            to={loginPath}
            className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
          >
            {language === 'en' ? 'Sign in to run scanner' : '登录后运行扫描器'}
          </Link>
        )}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]">
          <Card title={language === 'en' ? 'How the scanner fits the product' : '扫描器在产品中的位置'} subtitle={language === 'en' ? 'Role-aware boundary' : '角色边界'}>
            <div className="space-y-4">
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4 text-sm leading-6 text-secondary-text">
                {language === 'en'
                  ? 'Signed-in users get their own manual scanner runs, shortlist detail, and handoff into analysis or backtest without sharing history with other accounts.'
                  : '登录用户只会看到自己的手动扫描结果、shortlist 详情，以及通向分析或回测的个人化工作流，不再与其他账户共享历史。'}
              </div>
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4 text-sm leading-6 text-secondary-text">
                {language === 'en'
                  ? 'Admin-only watchlists, schedules, daily operational status, and operator history remain outside the guest and standard-user scanner surface.'
                  : '管理员专属的系统 watchlist、调度、运营状态与 operator 历史继续留在 guest 和普通用户扫描器之外。'}
              </div>
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4 text-sm leading-6 text-secondary-text">
                {language === 'en'
                  ? 'The scanner preview is intentionally explanatory instead of live-running, so guests cannot create shared operational state.'
                  : '这个预告页刻意只做说明而不执行 live run，确保游客不会创建共享的运营状态。'}
              </div>
            </div>
          </Card>

          <Card title={language === 'en' ? 'What unlocks after sign-in' : '登录后会解锁什么'} subtitle={language === 'en' ? 'Next step' : '下一步'}>
            <div className="space-y-3">
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[hsl(var(--accent-warning-hsl)/0.3)] bg-[hsl(var(--accent-warning-hsl)/0.14)] text-[hsl(var(--accent-warning-hsl))]">
                    <ShieldAlert className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {language === 'en' ? 'Personal scanner workspace' : '个人扫描工作区'}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted-text">
                      {language === 'en'
                        ? 'Run manual scans, keep your own shortlist history, and send candidates into analysis or backtest.'
                        : '执行手动扫描、保留自己的 shortlist 历史，并把候选直接送进分析或回测。'}
                    </p>
                  </div>
                </div>
              </div>
              <Link
                to={loginPath}
                className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
              >
                {language === 'en' ? 'Sign in now' : '立即登录'}
              </Link>
              <Link
                to={registrationPath}
                className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
              >
                {language === 'en' ? 'Create account' : '创建账户'}
              </Link>
            </div>
          </Card>
        </div>
      </WorkspacePageHeader>

      <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-4">
        <LockedFeatureCard
          icon={Radar}
          title={language === 'en' ? 'Manual runs' : '手动运行'}
          body={language === 'en' ? 'Generate a scanner run under your own account instead of creating anonymous shared state.' : '在你自己的账户下执行扫描，而不是创建匿名共享状态。'}
          lockedLabel={language === 'en' ? 'Locked' : '已锁定'}
          ctaLabel={language === 'en' ? 'Sign in' : '登录'}
          ctaTo={loginPath}
        />
        <LockedFeatureCard
          icon={History}
          title={language === 'en' ? 'Saved watchlists' : '保存观察名单'}
          body={language === 'en' ? 'Review your own historical runs, shortlist changes, and follow-through decisions.' : '查看你自己的历史 run、shortlist 变化和后续执行决策。'}
          lockedLabel={language === 'en' ? 'Locked' : '已锁定'}
          ctaLabel={language === 'en' ? 'Sign in' : '登录'}
          ctaTo={loginPath}
        />
        <LockedFeatureCard
          icon={BarChart3}
          title={language === 'en' ? 'Review context' : '复盘上下文'}
          body={language === 'en' ? 'See review status and performance context once runs belong to a registered identity.' : '当 run 归属于注册身份后，才能看到复盘状态和表现上下文。'}
          lockedLabel={language === 'en' ? 'Locked' : '已锁定'}
          ctaLabel={language === 'en' ? 'Sign in' : '登录'}
          ctaTo={loginPath}
        />
        <LockedFeatureCard
          icon={TestTubeDiagonal}
          title={language === 'en' ? 'Backtest handoff' : '回测联动'}
          body={language === 'en' ? 'Push candidates into deterministic backtests and keep the results in your own workspace.' : '把候选送入确定性回测，并将结果保存到你的个人工作区。'}
          lockedLabel={language === 'en' ? 'Locked' : '已锁定'}
          ctaLabel={language === 'en' ? 'Open home preview' : '回到首页预览'}
          ctaTo="/"
        />
      </div>
    </div>
  );
};

export default GuestScannerPage;
