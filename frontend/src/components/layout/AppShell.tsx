import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { ValidationBanner, WarningProvider } from "./ValidationBanner";

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  return (
    <WarningProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-indigo-700 focus:shadow-card"
      >
        Skip to content
      </a>
      <div className="min-h-screen bg-white [--header-h:100px]">
        <header className="sticky top-0 z-30">
          <TopBar onMenu={() => setMenuOpen(true)} />
          <ValidationBanner />
        </header>
        <div className="flex">
          <Sidebar open={menuOpen} onClose={closeMenu} />
          <main id="main" className="min-w-0 flex-1 bg-surface-alt">
            <div className="mx-auto w-full max-w-page px-4 py-6 sm:px-6 lg:py-8">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </WarningProvider>
  );
}
