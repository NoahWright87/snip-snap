import { Header, Heading, Layout } from "@noahwright/design";
import { Link, Route, Routes } from "react-router-dom";
import AnalysisBanner from "./components/AnalysisBanner";
import FfmpegBanner from "./components/FfmpegBanner";
import EditorView from "./pages/EditorView";
import LibraryView from "./pages/LibraryView";

export default function App() {
  return (
    <Layout
      header={
        <Header
          left={
            <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
              <Heading level={2}>¡Snip Snap! ✂️🫰</Heading>
            </Link>
          }
        />
      }
    >
      <FfmpegBanner />
      <AnalysisBanner />
      <div style={{ padding: "1.5rem", maxWidth: 1100, margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<LibraryView />} />
          <Route path="/videos/:id" element={<EditorView />} />
        </Routes>
      </div>
    </Layout>
  );
}
