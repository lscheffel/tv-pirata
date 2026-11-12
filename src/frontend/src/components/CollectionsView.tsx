import React, { useState, useEffect } from "react";
import { Layers, Tag, Plus, Star, FolderPlus } from "lucide-react";
import { CollectionRecord, ShowRecord, TagRecord, UnifiedShow } from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";

interface CollectionsViewProps {
  onOpenDetails: (show: UnifiedShow) => void;
}

export const CollectionsView: React.FC<CollectionsViewProps> = ({
  onOpenDetails,
}) => {
  const { showToast } = useToast();
  const [tags, setTags] = useState<TagRecord[]>([]);
  const [collections, setCollections] = useState<CollectionRecord[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<CollectionRecord | null>(null);
  const [collectionItems, setCollectionItems] = useState<ShowRecord[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);

  // New Tag form state
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#d81f26");

  // New Collection form state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCollName, setNewCollName] = useState("");
  const [newCollDesc, setNewCollDesc] = useState("");
  const [filterGenre, setFilterGenre] = useState("");
  const [filterMinRating, setFilterMinRating] = useState("7.0");

  const loadData = () => {
    api.collections
      .getTags()
      .then((data) => setTags(data))
      .catch((err) => console.error("Erro ao carregar tags:", err));

    api.collections
      .getSmartCollections()
      .then((data) => {
        setCollections(data);
        if (data.length > 0 && !selectedCollection) {
          setSelectedCollection(data[0]);
        }
      })
      .catch((err) => console.error("Erro ao carregar coleções:", err));
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!selectedCollection) return;
    setLoadingItems(true);
    api.collections
      .getSmartItems(selectedCollection.id)
      .then((items) => setCollectionItems(items))
      .catch((err) => {
        console.error("Erro ao carregar itens da coleção:", err);
        setCollectionItems([]);
      })
      .finally(() => setLoadingItems(false));
  }, [selectedCollection]);

  const handleCreateTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTagName.trim()) return;

    try {
      const created = await api.collections.createTag(newTagName.trim(), newTagColor);
      setTags((prev) => [...prev, created]);
      setNewTagName("");
      showToast(`Tag "${created.name}" criada com sucesso!`, "success");
    } catch {
      showToast("Erro ao criar tag", "error");
    }
  };

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCollName.trim()) return;

    const criteriaObj: Record<string, any> = {};
    if (filterGenre.trim()) criteriaObj.genre = filterGenre.trim();
    if (filterMinRating) criteriaObj.min_rating = parseFloat(filterMinRating);

    try {
      const created = await api.collections.createSmartCollection(
        newCollName.trim(),
        newCollDesc.trim(),
        JSON.stringify(criteriaObj)
      );
      setCollections((prev) => [...prev, created]);
      setSelectedCollection(created);
      setShowCreateModal(false);
      setNewCollName("");
      setNewCollDesc("");
      showToast(`Coleção inteligente "${created.name}" criada!`, "success");
    } catch {
      showToast("Erro ao criar coleção inteligente", "error");
    }
  };

  const convertToUnified = (s: ShowRecord): UnifiedShow => ({
    id: s.tmdb_id || s.id,
    tmdb_id: s.tmdb_id,
    tvmaze_id: s.tvmaze_id || undefined,
    imdb_id: s.imdb_id || undefined,
    title: s.title,
    original_title: s.original_title || undefined,
    overview: s.overview,
    poster_url: s.poster_url || undefined,
    backdrop_url: s.backdrop_url || undefined,
    rating: s.rating,
    genres: s.genres ? s.genres.split(",").map((g) => g.trim()) : [],
    first_air_date: s.first_air_date || undefined,
    status: s.status || undefined,
    source_provider: "collection",
    seasons: [],
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
            <Layers className="w-8 h-8 text-brand-red" />
            Coleções Inteligentes & Tags
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Filtros dinâmicos em JSON e classificação taxonômica da sua biblioteca
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-red hover:bg-brand-redHover text-white text-sm font-bold shadow-cinema-glow transition-all active:scale-95"
        >
          <FolderPlus className="w-4 h-4" />
          Nova Coleção Inteligente
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Left Column: Tags and Collections Sidebar */}
        <div className="space-y-6">
          {/* Smart Collections List */}
          <div className="bg-surface rounded-2xl border border-white/5 p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Coleções Salvas
            </h3>

            {collections.length === 0 ? (
              <p className="text-xs text-slate-500 py-3">Nenhuma coleção criada ainda.</p>
            ) : (
              <div className="space-y-1.5">
                {collections.map((coll) => (
                  <button
                    key={coll.id}
                    onClick={() => setSelectedCollection(coll)}
                    className={`w-full text-left px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-all flex items-center justify-between ${
                      selectedCollection?.id === coll.id
                        ? "bg-brand-red text-white shadow-cinema-glow"
                        : "text-slate-300 hover:bg-surface-elevated hover:text-white"
                    }`}
                  >
                    <span className="truncate">{coll.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Tags Widget */}
          <div className="bg-surface rounded-2xl border border-white/5 p-4 space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Tag className="w-4 h-4 text-yellow-400" />
              Tags do Acervo
            </h3>

            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <span
                  key={tag.id}
                  style={{ backgroundColor: `${tag.color}25`, borderColor: `${tag.color}60`, color: tag.color }}
                  className="px-2.5 py-1 rounded-lg text-xs font-bold border"
                >
                  #{tag.name}
                </span>
              ))}
            </div>

            {/* Quick create tag */}
            <form onSubmit={handleCreateTag} className="flex gap-2 pt-2 border-t border-white/5">
              <input
                type="text"
                placeholder="Nova tag..."
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                className="flex-1 bg-surface-elevated border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-red"
              />
              <input
                type="color"
                value={newTagColor}
                onChange={(e) => setNewTagColor(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0 p-0"
              />
              <button
                type="submit"
                className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Selected Collection Content */}
        <div className="lg:col-span-3 space-y-4">
          {selectedCollection ? (
            <div>
              <div className="mb-4">
                <h2 className="text-xl font-bold text-white">{selectedCollection.name}</h2>
                {selectedCollection.description && (
                  <p className="text-sm text-slate-400">{selectedCollection.description}</p>
                )}
                <div className="mt-2 inline-block px-2.5 py-1 rounded-md bg-surface-elevated text-xs font-mono text-cyan-300">
                  Critérios: {selectedCollection.filter_criteria}
                </div>
              </div>

              {loadingItems ? (
                <div className="py-20 text-center text-slate-500 animate-pulse">
                  Filtrando títulos da coleção...
                </div>
              ) : collectionItems.length === 0 ? (
                <div className="py-16 text-center rounded-2xl border border-dashed border-white/10 bg-surface/40 p-8 space-y-2">
                  <p className="text-sm font-semibold text-slate-300">
                    Nenhuma série na biblioteca atende a estes critérios de filtro.
                  </p>
                  <p className="text-xs text-slate-500">
                    Adicione mais títulos compatíveis na sua biblioteca pessoal!
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                  {collectionItems.map((item) => {
                    const unified = convertToUnified(item);

                    return (
                      <div
                        key={item.id}
                        onClick={() => onOpenDetails(unified)}
                        className="group relative flex flex-col rounded-xl overflow-hidden bg-surface border border-white/5 hover:border-white/15 cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="relative aspect-[2/3] w-full bg-surface-elevated">
                          {item.poster_url ? (
                            <img
                              src={item.poster_url}
                              alt={item.title}
                              loading="lazy"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center p-2 text-xs text-slate-500 text-center">
                              {item.title}
                            </div>
                          )}
                          {item.rating > 0 && (
                            <div className="absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 rounded bg-black/75 text-yellow-400 text-xs font-bold">
                              <Star className="w-3 h-3 fill-yellow-400" />
                              {item.rating.toFixed(1)}
                            </div>
                          )}
                        </div>
                        <div className="p-2.5">
                          <h4 className="text-xs font-bold text-white truncate">{item.title}</h4>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="py-24 text-center text-slate-500">
              Selecione ou crie uma coleção inteligente para visualizar os títulos filtrados.
            </div>
          )}
        </div>
      </div>

      {/* Modal Criar Coleção Inteligente */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
          <div className="relative w-full max-w-md bg-surface rounded-2xl border border-white/10 p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FolderPlus className="w-5 h-5 text-brand-red" />
              Nova Coleção Inteligente
            </h3>

            <form onSubmit={handleCreateCollection} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase">Nome da Coleção</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Melhores Sci-Fi"
                  value={newCollName}
                  onChange={(e) => setNewCollName(e.target.value)}
                  className="w-full mt-1 bg-surface-elevated border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-red"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase">Descrição (Opcional)</label>
                <input
                  type="text"
                  placeholder="Ex: Séries espaciais com nota alta"
                  value={newCollDesc}
                  onChange={(e) => setNewCollDesc(e.target.value)}
                  className="w-full mt-1 bg-surface-elevated border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-red"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase">Gênero Filtro</label>
                  <input
                    type="text"
                    placeholder="Ex: Drama, Sci-Fi"
                    value={filterGenre}
                    onChange={(e) => setFilterGenre(e.target.value)}
                    className="w-full mt-1 bg-surface-elevated border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-red"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase">Nota Mínima</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="10"
                    value={filterMinRating}
                    onChange={(e) => setFilterMinRating(e.target.value)}
                    className="w-full mt-1 bg-surface-elevated border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-red"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-white/5">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-400 hover:text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-brand-red hover:bg-brand-redHover text-white text-sm font-bold shadow-cinema-glow"
                >
                  Salvar Coleção
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

