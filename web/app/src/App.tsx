import { Routes, Route, Outlet } from 'react-router-dom';
import { Navigation } from './sections/Navigation';
import { Hero } from './sections/Hero';
import { Stats } from './sections/Stats';
import { HowItWorks } from './sections/HowItWorks';
import { FeatureStrip } from './sections/FeatureStrip';
import { Toolkit } from './sections/Toolkit';
import { StudioPreview } from './sections/StudioPreview';
import { FinalCTA } from './sections/FinalCTA';
import { Testimonial } from './sections/Testimonial';
import { Footer } from './sections/Footer';
import Studio from './pages/Studio';
import ArchgenCAD from './pages/ArchgenCAD';
import Services from './pages/Services';
import SignIn from './pages/SignIn';
import Demo from './pages/Demo';
import About from './pages/About';

function LandingPage() {
  return (
    <>
      <Hero />
      <Stats />
      <HowItWorks />
      <FeatureStrip />
      <Toolkit />
      <StudioPreview />
      <Testimonial />
      <FinalCTA />
    </>
  );
}

function GlobalLayout() {
  return (
    <div className="min-h-screen bg-[#0D1117] noise-overlay flex flex-col">
      <Navigation />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route element={<GlobalLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/archgencad" element={<ArchgenCAD />} />
        <Route path="/services" element={<Services />} />
        <Route path="/signin" element={<SignIn />} />
        <Route path="/demo" element={<Demo />} />
        <Route path="/about" element={<About />} />
      </Route>
      <Route path="/studio" element={<Studio />} />
    </Routes>
  );
}

export default App;
