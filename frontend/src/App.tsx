import { Header, Heading, Layout } from "@noahwright/design";
import { Link, Route, Routes } from "react-router-dom";
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
              <Heading level={2}>snip-snap</Heading>
            </Link>
          }
        />
      }
    >
      <FfmpegBanner />
      <div style={{ padding: "1.5rem", maxWidth: 1100, margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<LibraryView />} />
          <Route path="/videos/:id" element={<EditorView />} />
        </Routes>
      </div>
    </Layout>
  );
}
