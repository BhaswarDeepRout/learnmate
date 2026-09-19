import api from "./client";

export const aiTutorAPI = {
  getHistory: async () => {
    const response = await api.get("/ai-tutor/history");
    return response.data;
  },

  solveDoubt: async (query: string, topicContext: string = "") => {
    const response = await api.post("/ai-tutor/solve", {
      query,
      topic_context: topicContext
    });
    return response.data;
  }
};

